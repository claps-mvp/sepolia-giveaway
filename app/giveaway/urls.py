from django.urls import path
from . import views

urlpatterns = [
    path("fund/", views.FundView.as_view(), name="fund"),
    path("stats/", views.StatsView.as_view(), name="stats"),
]
