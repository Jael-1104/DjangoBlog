import logging
import os

import openai

from servermanager.models import commands

logger = logging.getLogger(__name__)

# zym：模块加载即从环境变量取 OpenAI 配置（旧式全局赋值，2.x SDK 下无效，见整改任务 E-2）
openai.api_key = os.environ.get('OPENAI_API_KEY')
if os.environ.get('HTTP_PROXY'):
    openai.proxy = os.environ.get('HTTP_PROXY')


class ChatGPT:
    # zym：AI 对话封装（当前调用 openai 旧 API，需切 DeepSeek，见 E-2）

    @staticmethod
    def chat(prompt):
        # zym：异常被吞成“服务器出错了”，排障困难
        try:
            completion = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                      messages=[{"role": "user", "content": prompt}])
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(e)
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
        cmd = list(
            filter(
                lambda x: x.title.upper() == title.upper(),
                self.commands))
        if cmd:
            return self.__run_command__(cmd[0].command)
        else:
            return "未找到相关命令，请输入hepme获得帮助。"

    def __run_command__(self, cmd):
        # zym：os.popen 直接执行注册命令，无超时无审计（见 E-1）
        try:
            res = os.popen(cmd).read()
            return res
        except BaseException:
            return '命令执行出错!'

    def get_help(self):
        # zym：列出所有命令标题与描述
        rsp = ''
        for cmd in self.commands:
            rsp += '{c}:{d}\n'.format(c=cmd.title, d=cmd.describe)
        return rsp


# zym：模块级误跑块，导入即会触发对话，建议移除
if __name__ == '__main__':
    chatbot = ChatGPT()
    prompt = "写一篇1000字关于AI的论文"
    print(chatbot.chat(prompt))
