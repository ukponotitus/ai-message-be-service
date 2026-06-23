from django.contrib import admin
from .models import Transaction, Subscription

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["business", "reference", "amount", "plan_type", "billing_cycle", "status", "created_at"]
    list_filter = ["status", "plan_type", "billing_cycle"]
    search_fields = ["reference", "business__name"]

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["business", "plan", "billing_cycle", "expires_at", "is_active"]
    list_filter = ["plan", "billing_cycle", "is_active"]
