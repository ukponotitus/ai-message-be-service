from django.urls import path
from .views import ConversationDetailAPI, DashboardMetricsAPI, DashboardAnalyticsAPI, DashboardLogsAPI

urlpatterns = [
    path('metrics/', DashboardMetricsAPI.as_view()),
    path('analytics/', DashboardAnalyticsAPI.as_view()),
    path('logs/', DashboardLogsAPI.as_view()),
    path('conversation/<str:identifier>/', ConversationDetailAPI.as_view()),

]