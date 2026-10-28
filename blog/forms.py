import logging

from django import forms
from haystack.forms import SearchForm

logger = logging.getLogger(__name__)


# wjq：Haystack 搜索表单，附加必填查询字段；无有效查询返回“未找到”
class BlogSearchForm(SearchForm):
    querydata = forms.CharField(required=True)

    def search(self):
        datas = super(BlogSearchForm, self).search()
        if not self.is_valid():
            return self.no_query_found()

        if self.cleaned_data['querydata']:
            logger.info(self.cleaned_data['querydata'])
        return datas
