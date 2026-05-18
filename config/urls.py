from django.urls import path, include

urlpatterns = [
    path("", include("care_plan.urls")),
]
