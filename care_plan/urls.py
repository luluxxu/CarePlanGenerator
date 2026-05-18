from django.urls import path
from . import views

urlpatterns = [
    path("", views.form, name="form"),
    path("generate/", views.generate, name="generate"),
]
