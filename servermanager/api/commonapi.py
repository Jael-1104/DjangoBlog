import logging
import os
import subprocess

from openai import OpenAI

from servermanager.models import commands

logger = logging.getLogger(__name__)

# zym：模块加载即从环境变量取 OpenAI 配置（旧式全局赋值，2.x SDK 下无效，见整改任务 E-2）
# zym：E-2 已移除模块级 openai.api_key / openai.proxy 赋值，改为 _get_chat_client() 懒加载

# zym：DeepSeek 接入参数（E-2），均可用环境变量覆盖
DEFAULT_DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEFAULT_DEEPSEEK_MODEL = 'deepseek-chat'
CHAT_TIMEOUT = 30
# zym：命令执行超时秒数（E-1），避免异常命令长期占住 worker
COMMAND_TIMEOUT = 30
CHAT_UNAVAILABLE_HINT = 'AI 对话未配置，请先设置环境变量 DJANGO_DEEPSEEK_API_KEY。'

_chat_client = None


def _get_chat_client():
    """
    zym：懒加载指向 DeepSeek 的 OpenAI 兼容客户端（E-2）
    - 未配置 DJANGO_DEEPSEEK_API_KEY 时返回 None，由调用方优雅降级，不发起网络请求
    - 代理由 httpx 的 trust_env 从 HTTP_PROXY/HTTPS_PROXY 环境变量读取，无需手动设置
    """
    global _chat_client
    if _chat_client is not None:
        return _chat_client
    api_key = os.environ.get('DJANGO_DEEPSEEK_API_KEY')
    if not api_key:
        return None
    _chat_client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get('DEEPSEEK_BASE_URL') or DEFAULT_DEEPSEEK_BASE_URL,
        timeout=CHAT_TIMEOUT,
    )
    return _chat_client


class ChatGPT:
    # zym：AI 对话封装（当前调用 openai 旧 API，需切 DeepSeek，见 E-2）
    # zym：E-2 已切到 openai 2.x 的 client.chat.completions，base_url 指向 DeepSeek

    @staticmethod
    def chat(prompt):
        # zym：异常被吞成“服务器出错了”，排障困难
        # zym：未配置密钥时直接返回提示，既不发请求也不抛异常（微信端仍能收到可读回复）
        client = _get_chat_client()
        if client is None:
            logger.warning('DJANGO_DEEPSEEK_API_KEY 未配置，AI 对话已跳过')
            return CHAT_UNAVAILABLE_HINT
        try:
            completion = client.chat.completions.create(
                model=os.environ.get('DEEPSEEK_MODEL') or DEFAULT_DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.choices[0].message.content or 'AI 未返回内容'
        except Exception as e:
            # zym：logger.exception 保留堆栈，排障时能看到真实原因
            logger.exception('调用 DeepSeek 失败: %s', e)
            return "服务器出错了"


class CommandHandler:
    # zym：管理员命令执行器，命令来自后台注册表 commands
    def __init__(self):
        self.commands = commands.objects.all()

    def run(self, title):
        """
        运行命令
        :param title: 命令
        :return: 返回命令执行结果
        """
        # zym：按标题(不区分大小写)匹配已注册命令，命中才执行
        cmd = next(
            filter(lambda x: x.title.upper() == title.upper(), self.commands),
            None)
        if cmd is None:
            return "未找到相关命令，请输入hepme获得帮助。"
        # zym：传整个对象下去，审计日志才能带上命令 id 与 title
        return self.__run_command__(cmd)

    def __run_command__(self, cmd_obj):
        # zym：os.popen 直接执行注册命令，无超时无审计（见 E-1）
        # zym：E-1 改用 subprocess.run：超时可控、stdout/stderr 分离、执行可审计
        command = cmd_obj.command
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=COMMAND_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            logger.error('命令执行超时(%ss) id=%s title=%s command=%s',
                         COMMAND_TIMEOUT, cmd_obj.pk, cmd_obj.title, command)
            return '命令执行超时!'
        except Exception:
            # zym：不再用 except BaseException，避免吞掉 KeyboardInterrupt / SystemExit
            logger.exception('命令执行异常 id=%s title=%s command=%s',
                             cmd_obj.pk, cmd_obj.title, command)
            return '命令执行出错!'

        if completed.returncode != 0:
            logger.warning('命令执行失败 id=%s title=%s command=%s code=%s stderr=%s',
                           cmd_obj.pk, cmd_obj.title, command,
                           completed.returncode, (completed.stderr or '').strip())
        else:
            logger.info('命令执行成功 id=%s title=%s code=0',
                        cmd_obj.pk, cmd_obj.title)
        # zym：优先返回 stdout，为空时退回 stderr，避免微信端收到空回复
        return (completed.stdout or completed.stderr or '').strip() or '命令执行完成，无输出。'

    def get_help(self):
        # zym：列出所有命令标题与描述
        rsp = ''
        for cmd in self.commands:
            rsp += '{c}:{d}\n'.format(c=cmd.title, d=cmd.describe)
        return rsp


# zym：模块级误跑块，导入即会触发对话，建议移除
