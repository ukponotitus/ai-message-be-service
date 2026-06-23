from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import (
    Contact, Message, Business, BusinessMember, ChannelConnection,
    Conversation, Tag, ContactTag, CustomField, ContactCustomField,
    AutomationFlow, Broadcast, BroadcastRecipient, AnalyticsEvent, CompanyInfo,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "name", "date_joined"]

    def get_name(self, obj):
        return obj.first_name or obj.email.split("@")[0]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(required=False, default="")

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "name"]

    def create(self, validated_data):
        name = validated_data.pop("name", "")
        email = validated_data["email"]
        first_name = validated_data.get("first_name", "")
        last_name = validated_data.get("last_name", "")

        if name and not first_name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=first_name,
            last_name=last_name,
        )
        return user


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "name", "slug", "whatsapp_phone_number_id", "system_prompt", "is_active", "created_at"]

    def create(self, validated_data):
        validated_data.setdefault("whatsapp_access_token", "")
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("whatsapp_phone_number_id") is None:
            data["whatsapp_phone_number_id"] = ""
        return data


class BusinessOnboardSerializer(serializers.Serializer):
    name = serializers.CharField()
    industry = serializers.CharField(required=False, default="")
    channels = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    whatsapp_phone_number_id = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp_access_token = serializers.CharField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        from django.utils.text import slugify
        from django.db import IntegrityError
        base_slug = slugify(validated_data["name"]) or "business"
        slug = base_slug
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        phone_id = validated_data.get("whatsapp_phone_number_id", "") or None
        # Don't allow email-like values in a phone number field
        if phone_id and "@" in phone_id:
            phone_id = None

        try:
            business = Business.objects.create(
                name=validated_data["name"],
                slug=slug,
                is_active=True,
                whatsapp_phone_number_id=phone_id,
                whatsapp_access_token=validated_data.get("whatsapp_access_token", ""),
            )
        except IntegrityError as e:
            from rest_framework.exceptions import APIException
            raise APIException(f"Could not create business: {e}")

        try:
            from billing.models import Subscription
            Subscription.objects.get_or_create(business=business)
        except Exception:
            pass
        return business


class BusinessDetailSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    channel_count = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = ["id", "name", "slug", "whatsapp_phone_number_id", "system_prompt", "is_active", "created_at", "member_count", "channel_count"]

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def get_channel_count(self, obj):
        return obj.channels.filter(is_active=True).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("whatsapp_phone_number_id") is None:
            data["whatsapp_phone_number_id"] = ""
        return data


class BusinessMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    business = BusinessSerializer(read_only=True)

    class Meta:
        model = BusinessMember
        fields = ["id", "user", "business", "role", "is_active", "created_at"]


class ChannelConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelConnection
        fields = ["id", "business", "channel_type", "name", "phone_number_id", "status", "is_active", "created_at", "updated_at"]
        read_only_fields = ["business"]


class ChannelConnectionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelConnection
        fields = ["id", "business", "channel_type", "name", "credentials", "phone_number_id", "access_token", "status", "webhook_verify_token", "is_active", "created_at", "updated_at"]
        read_only_fields = ["business"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "business", "name", "color"]
        read_only_fields = ["business"]


class ContactTagSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)

    class Meta:
        model = ContactTag
        fields = ["id", "tag", "created_at"]


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = ["id", "business", "name", "field_type"]
        read_only_fields = ["business"]


class ContactCustomFieldSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    field_type = serializers.CharField(source="field.field_type", read_only=True)

    class Meta:
        model = ContactCustomField
        fields = ["id", "field", "field_name", "field_type", "value"]


class ContactListSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    tags = ContactTagSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = ["id", "phone", "email", "name", "avatar_url", "notes", "is_blocked", "created_at", "updated_at", "message_count", "last_message", "tags"]

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        if last:
            return {"role": last.role, "content": last.content[:100], "created_at": last.created_at}
        return None


class ContactDetailSerializer(serializers.ModelSerializer):
    tags = ContactTagSerializer(many=True, read_only=True)
    custom_field_values = ContactCustomFieldSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = ["id", "business", "phone", "email", "name", "avatar_url", "notes", "is_blocked", "created_at", "updated_at", "tags", "custom_field_values"]


class ConversationListSerializer(serializers.ModelSerializer):
    contact = ContactListSerializer(read_only=True)
    channel_name = serializers.CharField(source="channel.name", read_only=True, default="")
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "contact", "channel", "channel_name", "status", "assigned_to", "is_ai_enabled", "last_message_at", "created_at", "last_message", "unread_count"]

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        if last:
            return {"role": last.role, "content": last.content[:150], "created_at": last.created_at}
        return None

    def get_unread_count(self, obj):
        return obj.messages.filter(role="user").count()


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "status", "response_time", "created_at", "contact", "conversation"]


class MessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField()


class AutomationFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationFlow
        fields = ["id", "business", "name", "trigger", "trigger_keywords", "system_prompt", "is_active", "published_at", "created_at", "updated_at"]
        read_only_fields = ["business", "published_at"]


class BroadcastSerializer(serializers.ModelSerializer):
    contacts = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Broadcast
        fields = ["id", "business", "name", "channel", "channel_type", "email_subject", "message_content", "status", "scheduled_at", "sent_count", "failed_count", "total_count", "created_at", "updated_at", "contacts"]
        read_only_fields = ["business", "sent_count", "failed_count", "total_count"]


class BroadcastDetailSerializer(serializers.ModelSerializer):
    recipients = serializers.SerializerMethodField()
    contacts = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Broadcast
        fields = ["id", "business", "name", "channel", "channel_type", "email_subject", "message_content", "status", "scheduled_at", "sent_count", "failed_count", "total_count", "created_at", "updated_at", "recipients", "contacts"]

    def get_recipients(self, obj):
        return [
            {
                "contact_id": r.contact_id,
                "contact_name": r.contact.name,
                "contact_phone": r.contact.phone,
                "status": r.status,
                "error": r.error_message,
                "sent_at": r.sent_at,
            }
            for r in obj.recipients.all()[:50]
        ]


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = ["id", "business", "event_type", "channel", "contact", "metadata", "created_at"]
        read_only_fields = ["business"]


class CompanyInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyInfo
        fields = ["id", "business", "key", "content"]
        read_only_fields = ["business"]


class CompanyInfoFrontendSerializer(serializers.ModelSerializer):
    question = serializers.CharField(source="key")
    answer = serializers.CharField(source="content")

    class Meta:
        model = CompanyInfo
        fields = ["id", "business", "question", "answer"]
        read_only_fields = ["business"]



class CompanyInfoFrontendCreateSerializer(serializers.Serializer):
    question = serializers.CharField(required=False, allow_blank=True, default="")
    answer = serializers.CharField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        return CompanyInfo.objects.create(
            business_id=self.context["business_id"],
            key=validated_data.get("question", ""),
            content=validated_data.get("answer", ""),
        )


class ChannelConnectionFrontendSerializer(serializers.ModelSerializer):
    channel = serializers.CharField(source="channel_type")
    is_connected = serializers.SerializerMethodField()

    class Meta:
        model = ChannelConnection
        fields = ["id", "business", "channel", "is_connected", "phone_number_id", "access_token", "created_at"]

    def get_is_connected(self, obj):
        return obj.status == "active"


class ChannelConnectionConnectSerializer(serializers.Serializer):
    channel = serializers.CharField()
    phone_number_id = serializers.CharField(required=False, allow_blank=True)
    access_token = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        business_id = self.context["business_id"]
        channel_type = validated_data["channel"]
        phone_number_id = validated_data.get("phone_number_id", "")
        access_token = validated_data.get("access_token", "")

        from billing.services import check_channel_limit
        from automation.models import Business
        business = Business.objects.get(id=business_id)
        ok, used, limit = check_channel_limit(business)
        if not ok:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f"Channel limit reached ({used}/{limit}). Upgrade your plan to add more channels.")

        channel, _ = ChannelConnection.objects.get_or_create(
            business_id=business_id,
            channel_type=channel_type,
            defaults={
                "name": channel_type.title(),
                "status": "active",
                "phone_number_id": phone_number_id,
                "access_token": access_token,
            },
        )
        if phone_number_id:
            channel.phone_number_id = phone_number_id
        if access_token:
            channel.access_token = access_token
        if phone_number_id or access_token:
            channel.status = "active"
            channel.save(update_fields=["phone_number_id", "access_token", "status"])
        return channel


class ContactFrontendSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()
    assigned_agent = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = ["id", "business", "name", "phone", "email", "tags", "last_active", "assigned_agent", "message_count", "created_at"]

    def get_tags(self, obj):
        return [ct.tag.name for ct in obj.contact_tags.select_related("tag").all()]

    def get_last_active(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return last.created_at.isoformat() if last else None

    def get_assigned_agent(self, obj):
        return None

    def get_message_count(self, obj):
        return obj.messages.count()


class ContactCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        business_id = self.context["business_id"]
        return Contact.objects.create(
            business_id=business_id,
            name=validated_data.get("name", ""),
            phone=validated_data.get("phone", ""),
            email=validated_data.get("email", ""),
        )


class MessageFrontendSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Message
        fields = ["id", "business", "contact", "role", "content", "timestamp"]


class MessageCreateFrontendSerializer(serializers.Serializer):
    contact = serializers.IntegerField()
    role = serializers.CharField(default="assistant")
    content = serializers.CharField()

    def create(self, validated_data):
        business_id = self.context["business_id"]
        return Message.objects.create(
            business_id=business_id,
            contact_id=validated_data["contact"],
            role=validated_data.get("role", "assistant"),
            content=validated_data["content"],
        )


class BroadcastFrontendSerializer(serializers.ModelSerializer):
    channel = serializers.SerializerMethodField()
    content = serializers.CharField(source="message_content")
    audience_segment = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    contact_ids = serializers.SerializerMethodField()

    class Meta:
        model = Broadcast
        fields = [
            "id", "business", "name", "channel", "channel_type", "email_subject",
            "audience_segment", "content", "status", "scheduled_at", "sent_count",
            "delivered_count", "failed_count", "created_at", "contact_ids",
        ]
        read_only_fields = ["business", "sent_count", "delivered_count", "failed_count"]

    def get_channel(self, obj):
        return obj.channel_type or (obj.channel.channel_type if obj.channel else "whatsapp")

    def get_audience_segment(self, obj):
        return None

    def get_delivered_count(self, obj):
        return obj.sent_count

    def get_contact_ids(self, obj):
        return list(obj.contacts.values_list("id", flat=True))


class BroadcastCreateFrontendSerializer(serializers.Serializer):
    name = serializers.CharField()
    content = serializers.CharField()
    channel = serializers.CharField(default="whatsapp")
    email_subject = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(default="draft")
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    contact_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])

    def validate(self, data):
        if data.get("channel") == "email" and not data.get("email_subject"):
            raise serializers.ValidationError({"email_subject": "Email subject is required for email broadcasts."})
        return data

    def create(self, validated_data):
        business_id = self.context["business_id"]
        channel_type = validated_data.get("channel", "whatsapp")
        email_subject = validated_data.get("email_subject", "")
        contact_ids = validated_data.get("contact_ids", [])
        channel = None
        if channel_type != "email":
            channel = ChannelConnection.objects.filter(
                business_id=business_id, channel_type=channel_type, is_active=True
            ).first()
        broadcast = Broadcast.objects.create(
            business_id=business_id,
            name=validated_data["name"],
            channel_type=channel_type,
            email_subject=email_subject,
            message_content=validated_data["content"],
            channel=channel,
            status=validated_data.get("status", "draft"),
            scheduled_at=validated_data.get("scheduled_at"),
        )
        if contact_ids:
            broadcast.contacts.set(contact_ids)
        return broadcast


class BroadcastUpdateFrontendSerializer(serializers.Serializer):
    contact_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def update(self, instance, validated_data):
        contact_ids = validated_data.get("contact_ids")
        if contact_ids is not None:
            instance.contacts.set(contact_ids)
        return instance


class AutomationFrontendSerializer(serializers.ModelSerializer):
    steps = serializers.SerializerMethodField()

    class Meta:
        model = AutomationFlow
        fields = ["id", "business", "name", "trigger", "is_active", "steps", "created_at"]

    def get_steps(self, obj):
        return []


class WhatsAppProfileSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, default="")


class WhatsAppContactSerializer(serializers.Serializer):
    profile = WhatsAppProfileSerializer(required=False)
    wa_id = serializers.CharField()


class WhatsAppTextSerializer(serializers.Serializer):
    body = serializers.CharField()


class WhatsAppMessageSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    text = WhatsAppTextSerializer(required=False)

    def to_internal_value(self, data):
        internal = super().to_internal_value(data)
        from_number = data.get("from")
        if not from_number:
            raise serializers.ValidationError({"from": "This field is required."})
        internal["from_number"] = from_number
        return internal

    def validate(self, data):
        if data.get("type") != "text":
            raise serializers.ValidationError("Only text messages are supported.")
        if not data.get("text"):
            raise serializers.ValidationError("Text field is missing.")
        return data


class WhatsAppValueSerializer(serializers.Serializer):
    messages = WhatsAppMessageSerializer(many=True, required=False)
    contacts = WhatsAppContactSerializer(many=True, required=False)


class WhatsAppChangeSerializer(serializers.Serializer):
    value = WhatsAppValueSerializer()


class WhatsAppEntrySerializer(serializers.Serializer):
    changes = WhatsAppChangeSerializer(many=True)


class WebhookPayloadSerializer(serializers.Serializer):
    object = serializers.CharField()
    entry = WhatsAppEntrySerializer(many=True)

    def validate_object(self, value):
        if value != "whatsapp_business_account":
            raise serializers.ValidationError("Unexpected webhook object type.")
        return value

    def get_first_message(self):
        entry = self.validated_data["entry"][0]
        value = entry["changes"][0]["value"]
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if not messages:
            return None, None, None

        message = messages[0]
        contact_data = contacts[0] if contacts else {}
        sender_name = contact_data.get("profile", {}).get("name", "")
        from_number = message["from_number"]
        message_text = message["text"]["body"]

        return from_number, sender_name, message_text
