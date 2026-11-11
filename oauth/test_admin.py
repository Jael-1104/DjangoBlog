"""OAuth 后台测试：确认 AppSecret 不以明文出现在列表页"""
from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from oauth.admin import OAuthConfigAdmin
from oauth.models import OAuthConfig


class OAuthConfigAdminTest(TestCase):
    def setUp(self):
        self.admin = OAuthConfigAdmin(OAuthConfig, AdminSite())
        self.config = OAuthConfig.objects.create(
            type='github',
            appkey='test-app-key',
            appsecret='super-secret-value-1234',
            callback_url='http://example.com/oauth/callback'
        )

    def test_appsecret_not_in_list_display(self):
        """D-1 list_display 不再直接包含 appsecret 字段"""
        self.assertNotIn('appsecret', self.admin.list_display)

    def test_appsecret_masked(self):
        """D-1 列表展示为掩码，不含完整密钥"""
        masked = self.admin.masked_appsecret(self.config)
        self.assertIn('*', masked)
        self.assertTrue(masked.startswith('supe'))
        self.assertTrue(masked.endswith('1234'))
        self.assertNotIn('super-secret-value-1234', masked)

    def test_short_appsecret_fully_masked(self):
        """D-1 短密钥全部掩码"""
        self.config.appsecret = 'short'
        self.assertEqual(self.admin.masked_appsecret(self.config), '*****')

    def test_empty_appsecret(self):
        """D-1 空密钥不报错"""
        self.config.appsecret = ''
        self.assertEqual(self.admin.masked_appsecret(self.config), '')
