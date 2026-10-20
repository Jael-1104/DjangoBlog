import logging

logger = logging.getLogger(__name__)

# 全局钩子注册表：{钩子名称: [回调函数, ...]}
# 采用模块级单例，进程内所有插件共享同一份注册数据
_hooks = {}


def register(hook_name: str, callback: callable):
    """
    注册一个钩子回调。
    :param hook_name: 钩子名称（见 hook_constants.py 中的常量定义）
    :param callback: 可调用对象，Action 无返回值、Filter 需返回处理后的值
    """
    if hook_name not in _hooks:
        _hooks[hook_name] = []
    _hooks[hook_name].append(callback)
    logger.debug(f"Registered hook '{hook_name}' with callback '{callback.__name__}'")


def run_action(hook_name: str, *args, **kwargs):
    """
    执行一个 Action Hook（动作钩子）。
    按注册顺序依次执行所有回调，不回传值，用于"通知型"扩展（如计数、注入上下文）。
    单个回调异常会被捕获并记录日志，避免影响主流程与其他插件。
    """
    if hook_name in _hooks:
        logger.debug(f"Running action hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error running action hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)


def apply_filters(hook_name: str, value, *args, **kwargs):
    """
    执行一个 Filter Hook（过滤钩子）。
    将 value 依次"流水线式"传递给每个回调并接收其返回值，用于"修改型"扩展
    （最常见的是对文章渲染后 HTML 的改写，如 `the_content` 钩子）。
    :return: 经过所有回调链式处理后的最终值
    """
    if hook_name in _hooks:
        logger.debug(f"Applying filter hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                value = callback(value, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error applying filter hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)
    return value
