from django.urls import path

from . import views

app_name = "oauth"
# lt：授权回调(authorize)、发起登录(oauthlogin)、补邮箱/确认/绑定结果路由
urlpatterns = [
    path(
        r'oauth/authorize',
        views.authorize),
    path(
        r'oauth/requireemail/<int:oauthid>.html',
        views.RequireEmailView.as_view(),
        name='require_email'),
    path(
        r'oauth/emailconfirm/<int:id>/<sign>.html',
        views.emailconfirm,
        name='email_confirm'),
    path(
        r'oauth/bindsuccess/<int:oauthid>.html',
        views.bindsuccess,
        name='bindsuccess'),
    path(
        r'oauth/oauthlogin',
        views.oauthlogin,
        name='oauthlogin')]
