from django import forms
from django.forms import ModelForm

from .models import Comment


# swn：评论表单，仅暴露 body；parent_comment_id 为隐藏字段，供楼中楼
class CommentForm(ModelForm):
    parent_comment_id = forms.IntegerField(
        widget=forms.HiddenInput, required=False)

    class Meta:
        model = Comment
        fields = ['body']
