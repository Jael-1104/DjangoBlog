from django import template

register = template.Library()


# swn：从父评论递归展开其所有已启用子评论（楼中楼展平）
@register.simple_tag
def parse_commenttree(commentlist, comment):
    """获得当前评论子评论的列表
        用法: {% parse_commenttree article_comments comment as childcomments %}
    """
    datas = []

    def parse(c):
        childs = commentlist.filter(parent_comment=c, is_enable=True)
        for child in childs:
            datas.append(child)
            parse(child)

    parse(comment)
    return datas


# swn：渲染单条评论，ischild 决定缩进层级
@register.inclusion_tag('comments/tags/comment_item.html')
def show_comment_item(comment, ischild):
    """评论"""
    depth = 1 if ischild else 2
    return {
        'comment_item': comment,
        'depth': depth
    }
