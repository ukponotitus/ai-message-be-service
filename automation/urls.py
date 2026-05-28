# automation/urls.py
from django.urls import path
from .views import EmailWebhookView, WebhookView

urlpatterns = [
    path("webhook/", WebhookView.as_view(), name="webhook"),
    path('email-webhook/', EmailWebhookView.as_view()),
]