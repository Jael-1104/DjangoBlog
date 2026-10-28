from django.urls import path
from django.urls import re_path

from . import views
from .forms import LoginForm

# phy：app_name 为 accounts，但主 urls 以实例命名空间 'account' 挂载，全站统一用 account:xxx 反解
app_name = "accounts"

urlpatterns = [re_path(r'^login/$',
                       views.LoginView.as_view(success_url='/'),
                       name='login',
                       kwargs={'authentication_form': LoginForm}),
               re_path(r'^register/$',
                       views.RegisterView.as_view(success_url="/"),
                       name='register'),
               re_path(r'^logout/$',
                       views.LogoutView.as_view(),
                       name='logout'),
               path(r'account/result.html',
                    views.account_result,
                    name='result'),
               re_path(r'^forget_password/$',
                       views.ForgetPasswordView.as_view(),
                       name='forget_password'),
               re_path(r'^forget_password_code/$',
                       views.ForgetPasswordEmailCode.as_view(),
                       name='forget_password_code'),
               ]
