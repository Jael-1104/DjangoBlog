import typing
from datetime import timedelta

from django.core.cache import cache
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from djangoblog.utils import send_email

_code_ttl = timedelta(minutes=5)  # phy：验证码有效期 5 分钟
# phy：发码限流参数——同一 IP+邮箱 60 秒一次，单 IP 每日最多 10 次
_code_rate_window = 60
_code_rate_daily = 10


def get_client_ip(request) -> str:
    """获取请求来源 IP（未考虑反向代理，如部署在 Nginx 后需自行解析 X-Forwarded-For）"""
    return request.META.get('REMOTE_ADDR') or 'unknown'


def is_send_code_limited(ip: str, email: str) -> bool:
    """是否触发发码限流"""
    if cache.get(f'pwdcode:once:{ip}:{email}'):
        return True
    return cache.get(f'pwdcode:daily:{ip}', 0) >= _code_rate_daily


def mark_send_code(ip: str, email: str):
    """记录一次发码：写 60 秒冷却 + 累加当日计数"""
    cache.set(f'pwdcode:once:{ip}:{email}', 1, _code_rate_window)
    daily_key = f'pwdcode:daily:{ip}'
    cache.set(daily_key, cache.get(daily_key, 0) + 1, 24 * 60 * 60)


def send_verify_email(to_mail: str, code: str, subject: str = _("Verify Email")):
    """发送重设密码验证码
    Args:
        to_mail: 接受邮箱
        subject: 邮件主题
        code: 验证码
    """
    # phy：同步 SMTP 发送验证码邮件
    html_content = _(
        "You are resetting the password, the verification code is：%(code)s, valid within 5 minutes, please keep it "
        "properly") % {'code': code}
    send_email([to_mail], subject, html_content)


def verify(email: str, code: str) -> typing.Optional[str]:
    """验证code是否有效
    Args:
        email: 请求邮箱
        code: 验证码
    Return:
        如果有错误就返回错误str
    Node:
        这里的错误处理不太合理，应该采用raise抛出
        否测调用方也需要对error进行处理
    """
    # phy：从缓存取验证码比对，不符返回错误串（返回式而非抛异常）
    cache_code = get_code(email)
    if cache_code != code:
        return gettext("Verification code error")


def set_code(email: str, code: str):
    """设置code"""
    # phy：以 email 为 key 写缓存并设 TTL
    cache.set(email, code, _code_ttl.seconds)


def get_code(email: str) -> typing.Optional[str]:
    """获取code"""
    return cache.get(email)
