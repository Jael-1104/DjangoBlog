from haystack.query import SearchQuerySet

from blog.models import Article, Category


# zym：机器人侧查询博客数据的只读适配层（Haystack 搜索 + 分类/最新文章）
class BlogApi:
    def __init__(self):
        self.searchqueryset = SearchQuerySet()
        self.searchqueryset.auto_query('')
        self.__max_takecount__ = 8

    def search_articles(self, query):
        # zym：全文检索并 load_all 减少二次查询，限最多 8 条
        sqs = self.searchqueryset.auto_query(query)
        sqs = sqs.load_all()
        return sqs[:self.__max_takecount__]

    def get_category_lists(self):
        return Category.objects.all()

    def get_category_articles(self, categoryname):
        # zym：按分类名取文章，限 8 条
        articles = Article.objects.filter(category__name=categoryname)
        if articles:
            return articles[:self.__max_takecount__]
        return None

    def get_recent_articles(self):
        return Article.objects.all()[:self.__max_takecount__]
