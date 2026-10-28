from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from djangoblog.utils import get_current_site


# Create your models here.

# phy：自定义用户模型，继承 AbstractUser，通过 AUTH_USER_MODEL 指定
class BlogUser(AbstractUser):
    nickname = models.CharField(_('nick name'), max_length=100, blank=True)  # phy：昵称
    creation_time = models.DateTimeField(_('creation time'), default=now)  # phy：创建时间
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)  # phy：最后修改时间
    source = models.CharField(_('create source'), max_length=100, blank=True)  # phy：注册来源

    def get_absolute_url(self):
        # phy：作者详情页相对路径
        return reverse(
            'blog:author_detail', kwargs={
                'author_name': self.username})

    def __str__(self):
        return self.email

    def get_full_url(self):
        # phy：拼接带域名的绝对 URL（硬编码 https）
        site = get_current_site().domain
        url = "https://{site}{path}".format(site=site,
                                            path=self.get_absolute_url())
        return url

    class Meta:
        ordering = ['-id']
        verbose_name = _('user')
        verbose_name_plural = verbose_name
        get_latest_by = 'id'
