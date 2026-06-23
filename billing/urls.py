from django.urls import path
from .views import PaystackVerifyView, SubscriptionView, InitializePaymentView, SuperAdminSubscriptionView

urlpatterns = [
    path("billing/verify/", PaystackVerifyView.as_view(), name="billing-verify"),
    path("billing/subscription/", SubscriptionView.as_view(), name="billing-subscription"),
    path("billing/initialize/", InitializePaymentView.as_view(), name="billing-initialize"),
    path("admin/business/<int:business_id>/subscription/", SuperAdminSubscriptionView.as_view(), name="admin-subscription"),
]
