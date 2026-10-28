from django.apps import AppConfig


# lt：app 配置，无自定义 ready 逻辑
class OauthConfig(AppConfig):
    name = 'oauth'
