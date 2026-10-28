from django.urls import path
from werobot.contrib.django import make_view

from .robot import robot

app_name = "servermanager"
# zym：仅一个入口——把 werobot 视图挂到 /robot 接收微信回调
urlpatterns = [
    path(r'robot', make_view(robot)),

]
