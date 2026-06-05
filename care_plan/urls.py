from django.urls import path
from . import views
from django.http import HttpResponse

urlpatterns = [
    path("", views.form, name="form"),
    path("generate/", views.generate, name="generate"),
    path("hello/", lambda request: HttpResponse("Hi!")),
    path("care_plans/<str:care_plan_id>/", views.detail, name="care_plan_detail"),
]
