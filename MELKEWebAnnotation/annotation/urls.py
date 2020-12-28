from django.urls import path
from . import views
from django.conf.urls import url, include

app_name = 'annotation'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^result$', views.search_documents, name='result'),
    url(r'^', views.filter_entities, name='filter'),
]