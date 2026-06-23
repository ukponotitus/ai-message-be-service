from django.contrib import admin
from .models import (
    Business, BusinessMember, Contact, Message, CompanyInfo,
    ChannelConnection, Conversation, Tag, ContactTag, CustomField,
    ContactCustomField, AutomationFlow, Broadcast, BroadcastRecipient,
    AnalyticsEvent, SocialAccount,
)


class BusinessMemberInline(admin.TabularInline):
    model = BusinessMember
    extra = 1


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BusinessMemberInline]


class ScopedAdminMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        business_ids = request.user.business_memberships.filter(
            is_active=True
        ).values_list("business_id", flat=True)
        return qs.filter(business_id__in=business_ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "business" and not request.user.is_superuser:
            business_ids = request.user.business_memberships.filter(
                is_active=True
            ).values_list("business_id", flat=True)
            kwargs["queryset"] = Business.objects.filter(id__in=business_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "business") and not obj.business_id:
            business_ids = request.user.business_memberships.filter(
                is_active=True
            ).values_list("business_id", flat=True)
            if business_ids:
                obj.business_id = business_ids[0]
        super().save_model(request, obj, form, change)


@admin.register(ChannelConnection)
class ChannelConnectionAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "channel_type", "business", "status", "is_active"]
    list_filter = ["channel_type", "status"]


@admin.register(Contact)
class ContactAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "phone", "email", "business", "created_at"]
    list_filter = ["business", "is_blocked"]


@admin.register(Conversation)
class ConversationAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["contact", "business", "status", "assigned_to", "last_message_at"]
    list_filter = ["status"]


@admin.register(Message)
class MessageAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["contact", "role", "content", "status", "business", "created_at"]
    list_filter = ["business", "status", "role"]


@admin.register(CompanyInfo)
class CompanyInfoAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["key", "business"]
    list_filter = ["business"]


@admin.register(BusinessMember)
class BusinessMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "role", "is_active"]
    list_filter = ["role", "is_active", "business"]


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "provider", "provider_id", "created_at"]


@admin.register(Tag)
class TagAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "business", "color"]


@admin.register(CustomField)
class CustomFieldAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "business", "field_type"]


@admin.register(AutomationFlow)
class AutomationFlowAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "business", "trigger", "is_active", "published_at"]
    list_filter = ["trigger", "is_active"]


@admin.register(Broadcast)
class BroadcastAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["name", "business", "status", "sent_count", "failed_count", "scheduled_at"]
    list_filter = ["status"]


@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["broadcast", "contact", "status", "sent_at"]
    list_filter = ["status"]


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(ScopedAdminMixin, admin.ModelAdmin):
    list_display = ["event_type", "business", "created_at"]
    list_filter = ["event_type"]
