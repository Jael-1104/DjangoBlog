from django.urls import path

from . import views

app_name = "comments"
# swn：评论提交(postcomment)与表情反应(react)两条接口路由
urlpatterns = [
    path(
        'article/<int:article_id>/postcomment',
        views.CommentPostView.as_view(),
        name='postcomment'),
    path(
        'comment/<int:comment_id>/react',
        views.CommentReactionView.as_view(),
        name='comment_react'),
]
