import logging
import os
import uuid

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from haystack.views import SearchView

from blog.models import Article, Category, LinkShowType, Links, Tag
from comments.forms import CommentForm
from djangoblog.plugin_manage import hooks
from djangoblog.plugin_manage.hook_constants import ARTICLE_CONTENT_HOOK_NAME
from djangoblog.utils import cache, get_blog_setting, get_sha256
from djangoblog.constants import CacheTimeout
from djangoblog.mixins import (
    SlugCachedMixin,
    ArticleListMixin,
    OptimizedArticleQueryMixin,
    CachedListViewMixin,
    PageNumberMixin
)

logger = logging.getLogger(__name__)


# wjq：列表视图公共基类，子类只需实现 get_queryset_data / 缓存键
class ArticleListView(CachedListViewMixin, PageNumberMixin, ListView):
    """
    文章列表视图基类（重构版）

    使用 Mixin 简化代码，消除重复逻辑
    子类只需实现 get_queryset_data() 和 get_queryset_cache_key() 方法
    """
    # template_name属性用于指定使用哪个模板进行渲染
    template_name = 'blog/article_index.html'

    # context_object_name属性用于给上下文变量取名（在模板中使用该名字）
    context_object_name = 'article_list'

    # 页面类型，分类目录或标签列表等
    page_type = ''
    paginate_by = settings.PAGINATE_BY
    page_kwarg = 'page'
    link_type = LinkShowType.L

    def get_context_data(self, **kwargs):
        kwargs['linktype'] = self.link_type
        return super(ArticleListView, self).get_context_data(**kwargs)


# wjq：首页已发布文章列表 + 基础 SEO 数据
class IndexView(OptimizedArticleQueryMixin, ArticleListView):
    """
    首页视图（重构版）

    继承 OptimizedArticleQueryMixin 获得优化的查询方法
    """
    # 友情链接类型
    link_type = LinkShowType.I

    def get_queryset_data(self):
        # 使用 Mixin 提供的优化查询方法
        return self.get_optimized_article_queryset().filter(
            type='a', status='p'
        )

    def get_queryset_cache_key(self):
        return f'index_{self.page_number}'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        blog_setting = get_blog_setting()
        # 提供基础SEO数据
        context['seo_title'] = f"{blog_setting.site_name} | {blog_setting.site_description}"
        context['seo_description'] = blog_setting.site_seo_description
        context['seo_keywords'] = blog_setting.site_keywords
        return context


# wjq：详情页；组装父/子评论分页、生成 SEO、触发插件钩子
class ArticleDetailView(DetailView):
    '''
    文章详情页面
    - 负责：加载文章、组织评论分页、计算 SEO、触发插件钩子
    '''
    template_name = 'blog/article_detail.html'
    model = Article
    pk_url_kwarg = 'article_id'
    context_object_name = "article"

    def get_context_data(self, **kwargs):
        comment_form = CommentForm()

        # 性能优化：只查父评论(parent_comment=None)，通过 prefetch_related
        # 一次性预加载子评论及作者，避免 N+1 查询
        # wjq：仅取父评论 + 预加载，规避评论 N+1
        from comments.models import Comment
        parent_comments = Comment.objects.filter(
            article=self.object,
            parent_comment=None,
            is_enable=True
        ).select_related('author').prefetch_related(
            'comment_set__author'  # 预加载子评论及其作者
        ).order_by('-id')

        # 获取所有评论用于总数显示
        article_comments = self.object.comment_list()

        blog_setting = get_blog_setting()
        paginator = Paginator(parent_comments, blog_setting.article_comment_count)
        page = self.request.GET.get('comment_page', '1')
        if not page.isnumeric():
            page = 1
        else:
            page = int(page)
            if page < 1:
                page = 1
            if page > paginator.num_pages:
                page = paginator.num_pages

        p_comments = paginator.page(page)
        next_page = p_comments.next_page_number() if p_comments.has_next() else None
        prev_page = p_comments.previous_page_number() if p_comments.has_previous() else None

        if next_page:
            kwargs[
                'comment_next_page_url'] = self.object.get_absolute_url() + f'?comment_page={next_page}#commentlist-container'
        if prev_page:
            kwargs[
                'comment_prev_page_url'] = self.object.get_absolute_url() + f'?comment_page={prev_page}#commentlist-container'
        kwargs['form'] = comment_form
        kwargs['article_comments'] = article_comments
        kwargs['p_comments'] = p_comments
        kwargs['comment_count'] = len(
            article_comments) if article_comments else 0

        kwargs['next_article'] = self.object.next_article
        kwargs['prev_article'] = self.object.prev_article

        context = super(ArticleDetailView, self).get_context_data(**kwargs)
        article = self.object
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        from django.utils.html import strip_tags
        from django.utils.text import Truncator
        from djangoblog.utils import CommonMarkdown
        
        # wjq：SEO 描述按文章缓存，避免每次请求重复渲染 Markdown；Article.save 时失效
        seo_desc_key = f'article_seo_desc_{article.pk}'
        description = cache.get(seo_desc_key)
        if description is None:
            # 处理description：markdown -> HTML -> 纯文本，彻底去除格式
            html_content = CommonMarkdown.get_markdown(article.body)
            description = strip_tags(html_content)
            description = ' '.join(description.split())  # 规范化空白字符
            description = Truncator(description).chars(150, truncate='...')
            cache.set(seo_desc_key, description, CacheTimeout.HOUR_10)
        
        # 处理keywords：去除空格，用逗号分隔
        tags = [tag.name.strip() for tag in article.tags.all()]
        keywords = ", ".join(tags) if tags else blog_setting.site_keywords
        
        context['seo_title'] = f"{article.title} | {blog_setting.site_name}"
        context['seo_description'] = description
        context['seo_keywords'] = keywords
        
        # 触发插件钩子：允许插件向详情页上下文注入额外数据
        from djangoblog.plugin_manage.hook_constants import ARTICLE_DETAIL_LOAD
        hooks.run_action(ARTICLE_DETAIL_LOAD, article=article, context=context, request=self.request)

        # Action Hook：通知所有插件"文章正文已获取"（如浏览计数插件在此累加）
        hooks.run_action('after_article_body_get', article=article, request=self.request)
        return context


# wjq：分类归档页，聚合该分类及子分类下的已发布文章
class CategoryDetailView(SlugCachedMixin, OptimizedArticleQueryMixin, ArticleListView):
    """
    分类目录列表（重构版）

    使用 SlugCachedMixin 避免重复查询 Category
    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = "分类目录归档"
    slug_url_kwarg = 'category_name'
    slug_model = Category

    def get_queryset_data(self):
        # 使用 Mixin 缓存的对象，只查询一次
        category = self.get_slug_object()
        categorynames = [c.name for c in category.get_sub_categorys()]

        return self.get_optimized_article_queryset().filter(
            category__name__in=categorynames, status='p'
        )

    def get_queryset_cache_key(self):
        # 复用缓存的对象，不再重复查询数据库
        category = self.get_slug_object()
        return f'category_list_{category.name}_{self.page_number}'

    def get_context_data(self, **kwargs):
        category = self.get_slug_object()
        categoryname = category.name

        # wjq：名称可能为空，直接安全截取最后一段；不再用 except BaseException 吞掉所有异常
        categoryname = (categoryname or '').split('/')[-1]

        kwargs['page_type'] = CategoryDetailView.page_type
        kwargs['tag_name'] = categoryname
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{categoryname} | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览 {categoryname} 分类下的所有文章，共 {article_count} 篇文章。"
        kwargs['seo_keywords'] = f"{categoryname}, {blog_setting.site_keywords}"
        
        return super(CategoryDetailView, self).get_context_data(**kwargs)


# wjq：按作者 username 归档文章
class AuthorDetailView(OptimizedArticleQueryMixin, ArticleListView):
    """
    作者详情页（重构版）

    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = '作者文章归档'

    def get_queryset_cache_key(self):
        from uuslug import slugify
        author_name = slugify(self.kwargs['author_name'])
        return f'author_{author_name}_{self.page_number}'

    def get_queryset_data(self):
        author_name = self.kwargs['author_name']
        return self.get_optimized_article_queryset().filter(
            author__username=author_name, type='a', status='p'
        )

    def get_context_data(self, **kwargs):
        author_name = self.kwargs['author_name']
        kwargs['page_type'] = AuthorDetailView.page_type
        kwargs['tag_name'] = author_name
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{author_name} 的文章 | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览 {author_name} 发表的所有文章，共 {article_count} 篇。"
        kwargs['seo_keywords'] = f"{author_name}, {blog_setting.site_keywords}"
        
        return super(AuthorDetailView, self).get_context_data(**kwargs)


# wjq：按标签 slug 归档文章
class TagDetailView(SlugCachedMixin, OptimizedArticleQueryMixin, ArticleListView):
    """
    标签列表页面（重构版）

    使用 SlugCachedMixin 避免重复查询 Tag
    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = '分类标签归档'
    slug_url_kwarg = 'tag_name'
    slug_model = Tag

    def get_queryset_data(self):
        # 使用 Mixin 缓存的对象，只查询一次
        tag = self.get_slug_object()
        return self.get_optimized_article_queryset().filter(
            tags__name=tag.name, type='a', status='p'
        )

    def get_queryset_cache_key(self):
        # 复用缓存的对象，不再重复查询数据库
        tag = self.get_slug_object()
        return f'tag_{tag.name}_{self.page_number}'

    def get_context_data(self, **kwargs):
        tag = self.get_slug_object()
        kwargs['page_type'] = TagDetailView.page_type
        kwargs['tag_name'] = tag.name
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{tag.name} | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览所有关于 {tag.name} 的文章，共 {article_count} 篇内容。"
        kwargs['seo_keywords'] = f"{tag.name}, {blog_setting.site_keywords}"
        
        return super(TagDetailView, self).get_context_data(**kwargs)


# wjq：全站归档，不分页
class ArchivesView(OptimizedArticleQueryMixin, ArticleListView):
    """
    文章归档页面（重构版）

    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = '文章归档'
    paginate_by = None
    page_kwarg = None
    template_name = 'blog/article_archives.html'

    def get_queryset_data(self):
        return self.get_optimized_article_queryset().filter(status='p')

    def get_queryset_cache_key(self):
        return 'archives'


# wjq：友链列表页，仅展示启用项
class LinkListView(ListView):
    model = Links
    template_name = 'blog/links_list.html'

    def get_queryset(self):
        return Links.objects.filter(is_enable=True)


# wjq：Haystack 搜索视图，开启结果高亮并自定义上下文
class EsSearchView(SearchView):
    def build_form(self, form_kwargs=None):
        """Override to enable highlighting"""
        if form_kwargs is None:
            form_kwargs = {}

        # Enable highlighting for search results
        from haystack.query import SearchQuerySet
        if self.searchqueryset is None:
            sqs = SearchQuerySet().highlight()
        else:
            sqs = self.searchqueryset.highlight()

        form_kwargs['searchqueryset'] = sqs
        return super().build_form(form_kwargs=form_kwargs)

    def get_context(self):
        paginator, page = self.build_page()
        context = {
            "query": self.query,
            "form": self.form,
            "page": page,
            "paginator": paginator,
            "suggestion": None,
        }
        if hasattr(self.results, "query") and self.results.query.backend.include_spelling:
            context["suggestion"] = self.results.query.get_spelling_suggestion()
        context.update(self.extra_context())

        return context


# wjq：上传白名单与大小上限；只允许已知后缀写入静态目录
UPLOAD_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
UPLOAD_FILE_EXTENSIONS = {
    '.pdf', '.zip', '.7z', '.rar', '.txt', '.md',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
}
UPLOAD_MAX_SIZE = 10 * 1024 * 1024  # 10MB


def _upload_authorized(request):
    """wjq：上传鉴权——后台登录用户，或携带 sign 的外部工具调用端"""
    if request.user.is_authenticated and request.user.is_staff:
        return True
    sign = request.GET.get('sign')
    if not sign:
        return False
    return constant_time_compare(sign, get_sha256(get_sha256(settings.SECRET_KEY)))


# wjq：图床上传接口；staff 登录或 sign 鉴权，后缀白名单 + 大小上限 + 精确后缀判定
@csrf_exempt
def fileupload(request):
    """
    该方法需自己写调用端来上传图片，该方法仅提供图床功能
    :param request:
    :return:
    """
    if request.method != 'POST':
        return HttpResponseForbidden("only for post")
    if not _upload_authorized(request):
        return HttpResponseForbidden()

    response = []
    for filename in request.FILES:
        upload = request.FILES[filename]
        # wjq：空文件与超大文件直接拒绝，避免磁盘被灌满
        if not upload.size:
            return HttpResponseForbidden("empty file")
        if upload.size > UPLOAD_MAX_SIZE:
            return HttpResponseForbidden("file too large")

        # wjq：按后缀精确匹配白名单，替代原来 find() 子串包含（"x.jpg.php" 会被误判为图片）
        ext = os.path.splitext(str(filename))[1].lower()
        is_image = ext in UPLOAD_IMAGE_EXTENSIONS
        if not is_image and ext not in UPLOAD_FILE_EXTENSIONS:
            return HttpResponseForbidden("unsupported file type")

        timestr = timezone.now().strftime('%Y/%m/%d')
        base_dir = os.path.join(settings.STATICFILES, "image" if is_image else "files", timestr)
        os.makedirs(base_dir, exist_ok=True)
        savepath = os.path.normpath(os.path.join(base_dir, f"{uuid.uuid4().hex}{ext}"))
        if not savepath.startswith(os.path.normpath(base_dir) + os.sep):
            return HttpResponseForbidden("invalid path")

        with open(savepath, 'wb+') as wfile:
            for chunk in upload.chunks():
                wfile.write(chunk)
        if is_image:
            # wjq：后缀合法但内容不是真图片时，清理已落盘文件并返回 403，避免读图异常变 500 与垃圾文件残留
            from PIL import Image
            try:
                with Image.open(savepath) as image:
                    image.save(savepath, quality=20, optimize=True)
            except (OSError, ValueError, Image.DecompressionBombError):
                if os.path.exists(savepath):
                    os.remove(savepath)
                return HttpResponseForbidden("invalid image")
        response.append(static(savepath))
    return HttpResponse(response)


# ===== 错误处理视图 =====
# 注意：这些函数保留是为了向后兼容
# 实际实现已经移动到 djangoblog.error_views
# 可以在 urls.py 中直接引用新的实现

from djangoblog.error_views import (
    page_not_found_view,
    server_error_view,
    permission_denied_view
)


# wjq：清空全站缓存的运维接口；仅 staff 可调用且必须 POST，防止匿名/GET 触发缓存穿透
@staff_member_required
@require_POST
def clean_cache_view(request):
    cache.clear()
    return HttpResponse('ok')
