from django.urls import path
from apps.core.views import base_view

urlpatterns = [
    path('', base_view, name="base_view")
]