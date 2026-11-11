import os
import subprocess
from unittest import mock

from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from werobot.messages.messages import TextMessage

from accounts.models import BlogUser
from blog.models import Category, Article
from servermanager.api import commonapi
from servermanager.api.commonapi import ChatGPT
from .models import commands
from .robot import MessageHandler, CommandHandler
from .robot import search, category, recents


# Create your tests here.
class ServerManagerTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    def test_chat_gpt(self):
        content = ChatGPT.chat("你好")
        self.assertIsNotNone(content)

    def test_validate_comment(self):
        user = BlogUser.objects.create_superuser(
            email="liangliangyy1@gmail.com",
            username="liangliangyy1",
            password="liangliangyy1")

        self.client.login(username='liangliangyy1', password='liangliangyy1')

        c = Category()
        c.name = "categoryccc"
        c.save()

        article = Article()
        article.title = "nicetitleccc"
        article.body = "nicecontentccc"
        article.author = user
        article.category = c
        article.type = 'a'
        article.status = 'p'
        article.save()
        s = TextMessage([])
        s.content = "nice"
        rsp = search(s, None)
        rsp = category(None, None)
        self.assertIsNotNone(rsp)
        rsp = recents(None, None)
        self.assertTrue(rsp != '暂时还没有文章')

        cmd = commands()
        cmd.title = "test"
        cmd.command = "ls"
        cmd.describe = "test"
        cmd.save()

        cmdhandler = CommandHandler()
        rsp = cmdhandler.run('test')
        self.assertIsNotNone(rsp)
        s.source = 'u'
        s.content = 'test'
        msghandler = MessageHandler(s, {})

        # msghandler.userinfo.isPasswordSet = True
        # msghandler.userinfo.isAdmin = True
        msghandler.handler()
        s.content = 'y'
        msghandler.handler()
        s.content = 'idcard:12321233'
        msghandler.handler()
        s.content = 'weather:上海'
        msghandler.handler()
        s.content = 'admin'
        msghandler.handler()
        s.content = '123'
        msghandler.handler()

        s.content = 'exit'
        msghandler.handler()


class CommonApiTest(TestCase):
    """zym：E-1/E-2 改造后的行为验证，全部离线运行，不依赖真实 API 与真实命令"""

    def test_chat_without_api_key_returns_hint(self):
        # zym：未配置密钥时必须优雅降级，不发请求且返回非 None
        with mock.patch.object(commonapi, '_chat_client', None), \
                mock.patch.dict(os.environ, {'DJANGO_DEEPSEEK_API_KEY': ''}):
            self.assertEqual(ChatGPT.chat('你好'), commonapi.CHAT_UNAVAILABLE_HINT)

    def test_chat_uses_deepseek_client(self):
        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value.choices = [
            mock.Mock(message=mock.Mock(content='你好呀'))]
        with mock.patch.object(commonapi, '_chat_client', fake_client):
            self.assertEqual(ChatGPT.chat('你好'), '你好呀')
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs['messages'], [{'role': 'user', 'content': '你好'}])
        self.assertTrue(kwargs['model'])

    def test_chat_swallows_exception(self):
        # zym：上游异常仍返回可读文案，不把异常抛给微信处理链
        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError('boom')
        with mock.patch.object(commonapi, '_chat_client', fake_client):
            self.assertEqual(ChatGPT.chat('你好'), '服务器出错了')

    def test_command_timeout(self):
        commands.objects.create(title='slow', command='sleep 100', describe='slow')
        handler = CommandHandler()
        with mock.patch('servermanager.api.commonapi.subprocess.run',
                        side_effect=subprocess.TimeoutExpired('sleep 100', 30)):
            self.assertEqual(handler.run('slow'), '命令执行超时!')

    def test_command_nonzero_exit_returns_stderr(self):
        commands.objects.create(title='fail', command='exit 1', describe='fail')
        handler = CommandHandler()
        completed = subprocess.CompletedProcess(args='exit 1', returncode=1,
                                                stdout='', stderr='boom\n')
        with mock.patch('servermanager.api.commonapi.subprocess.run',
                        return_value=completed):
            self.assertEqual(handler.run('fail'), 'boom')

    def test_command_not_found(self):
        handler = CommandHandler()
        self.assertIn('未找到', handler.run('no-such-title'))
