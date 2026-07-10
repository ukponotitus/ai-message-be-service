from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    EmailWebhookView, TwilioWebhookView, WebhookView,
    ChannelListView, ChannelDetailView, ChannelTestView,
    CompanyInfoListView, CompanyInfoDetailView,
    BusinessOnboardView, BusinessCompanyInfoView,
    MessageListCreateView,
)
from .auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    MyBusinessesView,
    CreateBusinessView,
    BusinessDetailView,
    BusinessMemberListView,
    BusinessMemberDetailView,
)
from .inbox_views import (
    ConversationListView,
    ConversationMessagesView,
    ConversationReplyView,
    ConversationAssignView,
    ConversationDetailView,
    ContactListView,
    ContactDetailView,
    ContactTagsView,
    TagListView,
    CustomFieldListView,
)
from .automation_views import (
    AutomationListView,
    AutomationDetailView,
    AutomationPublishView,
    BroadcastListView,
    BroadcastDetailView,
    BroadcastScheduleView,
    BroadcastSendView,
)
from .analytics_views import (
    AnalyticsOverviewView,
    AnalyticsChannelsView,
    AnalyticsBroadcastsView,
    AnalyticsAutomationsView,
)
from .social_auth import GoogleLoginView, FacebookLoginView

urlpatterns = [
    # Webhooks
    path("webhook/", WebhookView.as_view(), name="webhook"),
    path("email-webhook/", EmailWebhookView.as_view()),
    path("twilio-webhook/", TwilioWebhookView.as_view()),

    # Auth
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
    path("auth/facebook/", FacebookLoginView.as_view(), name="auth-facebook"),

    # Workspace / Business
    path("auth/businesses/", MyBusinessesView.as_view(), name="auth-businesses"),
    path("auth/businesses/create/", CreateBusinessView.as_view(), name="auth-create-business"),
    path("business/", BusinessOnboardView.as_view(), name="business-onboard"),
    path("business/<int:business_id>/", BusinessDetailView.as_view(), name="business-detail"),
    path("business/<int:business_id>/members/", BusinessMemberListView.as_view(), name="business-members"),
    path("business/<int:business_id>/members/<int:member_id>/", BusinessMemberDetailView.as_view(), name="business-member-detail"),
    path("business/<int:business_id>/company-info/", BusinessCompanyInfoView.as_view(), name="business-company-info"),

    # Channels
    path("channels/", ChannelListView.as_view(), name="channels"),
    path("channels/<int:channel_id>/", ChannelDetailView.as_view(), name="channel-detail"),
    path("channels/<int:channel_id>/test/", ChannelTestView.as_view(), name="channel-test"),

    # Messages (frontend inbox)
    path("messages/", MessageListCreateView.as_view(), name="messages"),

    # Inbox / Conversations
    path("conversations/", ConversationListView.as_view(), name="conversations"),
    path("conversations/<int:conversation_id>/messages/", ConversationMessagesView.as_view(), name="conversation-messages"),
    path("conversations/<int:conversation_id>/reply/", ConversationReplyView.as_view(), name="conversation-reply"),
    path("conversations/<int:conversation_id>/assign/", ConversationAssignView.as_view(), name="conversation-assign"),
    path("conversations/<int:conversation_id>/", ConversationDetailView.as_view(), name="conversation-detail"),

    # Contacts
    path("contacts/", ContactListView.as_view(), name="contacts"),
    path("contacts/<int:contact_id>/", ContactDetailView.as_view(), name="contact-detail"),
    path("contacts/<int:contact_id>/tags/", ContactTagsView.as_view(), name="contact-tags"),

    # Tags & Custom Fields
    path("tags/", TagListView.as_view(), name="tags"),
    path("custom-fields/", CustomFieldListView.as_view(), name="custom-fields"),

    # Knowledge Base
    path("company-info/", CompanyInfoListView.as_view(), name="company-info"),
    path("company-info/<int:info_id>/", CompanyInfoDetailView.as_view(), name="company-info-detail"),

    # Automations
    path("automations/", AutomationListView.as_view(), name="automations"),
    path("automations/<int:automation_id>/", AutomationDetailView.as_view(), name="automation-detail"),
    path("automations/<int:automation_id>/publish/", AutomationPublishView.as_view(), name="automation-publish"),

    # Broadcasts
    path("broadcasts/", BroadcastListView.as_view(), name="broadcasts"),
    path("broadcasts/<int:broadcast_id>/", BroadcastDetailView.as_view(), name="broadcast-detail"),
    path("broadcasts/<int:broadcast_id>/schedule/", BroadcastScheduleView.as_view(), name="broadcast-schedule"),
    path("broadcasts/<int:broadcast_id>/send/", BroadcastSendView.as_view(), name="broadcast-send"),

    # Analytics
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("analytics/channels/", AnalyticsChannelsView.as_view(), name="analytics-channels"),
    path("analytics/broadcasts/", AnalyticsBroadcastsView.as_view(), name="analytics-broadcasts"),
    path("analytics/automations/", AnalyticsAutomationsView.as_view(), name="analytics-automations"),
]
