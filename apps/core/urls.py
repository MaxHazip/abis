from django.urls import path
from . import views
# from apps.core.views import base_view

urlpatterns = [
    path('', views.MainView.as_view(), name="base_view"),
    path('feedback/', views.submit_form, name="feedback")
]