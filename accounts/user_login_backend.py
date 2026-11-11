from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """
    允许使用用户名或邮箱登录
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # phy：含 @ 走邮箱查询，否则走用户名查询
        # phy：username/password 为空时直接返回，避免 'in None' 抛 TypeError
        if username is None or password is None:
            return None
        if '@' in username:
            kwargs = {'email': username}
        else:
            kwargs = {'username': username}
        try:
            user = get_user_model().objects.get(**kwargs)
        except get_user_model().DoesNotExist:
            return None
        # phy：校验密码后复用 ModelBackend 的 user_can_authenticate，未激活用户不可登录
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, username):
        # phy：按主键取用户，供 session 反序列化
        try:
            return get_user_model().objects.get(pk=username)
        except get_user_model().DoesNotExist:
            return None
