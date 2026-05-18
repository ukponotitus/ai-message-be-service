from rest_framework import serializers
from .models import Contact, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]


class ContactSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = ["id", "phone", "name", "created_at", "messages"]


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
        """Extract the first message and sender from the validated payload."""
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