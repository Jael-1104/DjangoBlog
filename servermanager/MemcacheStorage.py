# zym：基于 Django cache 的 werobot 会话存储；以 JSON 序列化、key 加前缀
from werobot.session import SessionStorage
from werobot.utils import json_loads, json_dumps

from djangoblog.utils import cache


class MemcacheStorage(SessionStorage):
    def __init__(self, prefix='ws_'):
        self.prefix = prefix
        self.cache = cache

    @property
    def is_available(self):
        # zym：写入再读回探测缓存是否可用
        value = "1"
        self.set('checkavaliable', value=value)
        return value == self.get('checkavaliable')

    def key_name(self, s):
        return '{prefix}{s}'.format(prefix=self.prefix, s=s)

    def get(self, id):
        id = self.key_name(id)
        session_json = self.cache.get(id) or '{}'
        return json_loads(session_json)

    def set(self, id, value):
        id = self.key_name(id)
        self.cache.set(id, json_dumps(value))

    def delete(self, id):
        id = self.key_name(id)
        self.cache.delete(id)
