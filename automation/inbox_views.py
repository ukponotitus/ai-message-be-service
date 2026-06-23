from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q, Max
from django.utils import timezone

from .models import Contact, Message, Conversation, Tag, ContactTag, CustomField, ContactCustomField, Business, ChannelConnection
from .permissions import HasBusinessAccess, resolve_business_id
from .serializers import (
    ContactListSerializer, ContactDetailSerializer,
    ContactFrontendSerializer, ContactCreateSerializer, ContactTagSerializer,
    ConversationListSerializer, MessageSerializer, MessageCreateSerializer,
    TagSerializer, CustomFieldSerializer, ContactCustomFieldSerializer,
)


class ConversationListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        status_filter = request.query_params.get("status")
        search = request.query_params.get("search")

        qs = Conversation.objects.filter(business_id=business_id).select_related("contact", "channel")

        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(contact__name__icontains=search) |
                Q(contact__phone__icontains=search) |
                Q(contact__email__icontains=search)
            )

        qs = qs[:50]
        return Response(ConversationListSerializer(qs, many=True).data)


class ConversationMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request, conversation_id):
        business_id = resolve_business_id(request)
        conv = Conversation.objects.filter(id=conversation_id, business_id=business_id).first()
        if not conv:
            return Response({"error": "Conversation not found"}, status=404)

        messages = Message.objects.filter(conversation=conv).order_by("created_at")
        return Response(MessageSerializer(messages, many=True).data)


class ConversationReplyView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, conversation_id):
        business_id = resolve_business_id(request)
        conv = Conversation.objects.filter(id=conversation_id, business_id=business_id).first()
        if not conv:
            return Response({"error": "Conversation not found"}, status=404)

        serializer = MessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        content = serializer.validated_data["content"]
        channel = conv.channel

        msg = Message.objects.create(
            business_id=business_id,
            contact=conv.contact,
            conversation=conv,
            channel=channel,
            role="assistant",
            content=content,
            status="sent",
        )

        conv.last_message_at = timezone.now()
        conv.save(update_fields=["last_message_at"])

        if channel and channel.channel_type == "whatsapp" and conv.contact.phone:
            from .services import send_whatsapp_message
            business = Business.objects.get(id=business_id)
            send_whatsapp_message(business, conv.contact.phone, content)

        return Response(MessageSerializer(msg).data, status=201)


class ConversationAssignView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, conversation_id):
        business_id = resolve_business_id(request)
        conv = Conversation.objects.filter(id=conversation_id, business_id=business_id).first()
        if not conv:
            return Response({"error": "Conversation not found"}, status=404)

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        is_member = Business.objects.filter(
            id=business_id, members__user_id=user_id, members__is_active=True
        ).exists()

        if not is_member:
            return Response({"error": "User is not a member of this business"}, status=400)

        conv.assigned_to_id = user_id
        conv.save(update_fields=["assigned_to"])

        return Response({"status": "assigned", "assigned_to": user_id})


class ConversationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def patch(self, request, conversation_id):
        business_id = resolve_business_id(request)
        conv = Conversation.objects.filter(id=conversation_id, business_id=business_id).first()
        if not conv:
            return Response({"error": "Conversation not found"}, status=404)

        if "is_ai_enabled" in request.data:
            conv.is_ai_enabled = bool(request.data["is_ai_enabled"])
            conv.save(update_fields=["is_ai_enabled"])

        return Response({
            "id": conv.id,
            "is_ai_enabled": conv.is_ai_enabled,
        })


class ContactListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        search = request.query_params.get("search")

        qs = Contact.objects.filter(business_id=business_id)

        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )

        qs = qs.order_by("-created_at")[:100]
        return Response(ContactFrontendSerializer(qs, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = ContactCreateSerializer(data=request.data, context={"business_id": business_id})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        contact = serializer.save()
        return Response(ContactFrontendSerializer(contact).data, status=201)


class ContactDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request, contact_id):
        business_id = resolve_business_id(request)
        contact = Contact.objects.filter(id=contact_id, business_id=business_id).first()
        if not contact:
            return Response({"error": "Contact not found"}, status=404)

        return Response(ContactDetailSerializer(contact).data)

    def patch(self, request, contact_id):
        business_id = resolve_business_id(request)
        contact = Contact.objects.filter(id=contact_id, business_id=business_id).first()
        if not contact:
            return Response({"error": "Contact not found"}, status=404)

        allowed = ["name", "email", "phone", "avatar_url", "notes", "is_blocked"]
        for field in allowed:
            if field in request.data:
                setattr(contact, field, request.data[field])

        contact.save()
        return Response(ContactDetailSerializer(contact).data)


class ContactTagsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request, contact_id):
        business_id = resolve_business_id(request)
        contact = Contact.objects.filter(id=contact_id, business_id=business_id).first()
        if not contact:
            return Response({"error": "Contact not found"}, status=404)

        tags = ContactTag.objects.filter(contact=contact).select_related("tag")
        return Response(ContactTagSerializer(tags, many=True).data)

    def post(self, request, contact_id):
        business_id = resolve_business_id(request)
        contact = Contact.objects.filter(id=contact_id, business_id=business_id).first()
        if not contact:
            return Response({"error": "Contact not found"}, status=404)

        tag_id = request.data.get("tag_id")
        tag_name = request.data.get("tag_name")

        if tag_id:
            tag = Tag.objects.filter(id=tag_id, business_id=business_id).first()
        elif tag_name:
            tag, _ = Tag.objects.get_or_create(business_id=business_id, name=tag_name)
        else:
            return Response({"error": "tag_id or tag_name is required"}, status=400)

        if not tag:
            return Response({"error": "Tag not found"}, status=404)

        ContactTag.objects.get_or_create(contact=contact, tag=tag)
        return Response({"status": "tag_added", "tag": TagSerializer(tag).data})

    def delete(self, request, contact_id):
        business_id = resolve_business_id(request)
        contact = Contact.objects.filter(id=contact_id, business_id=business_id).first()
        if not contact:
            return Response({"error": "Contact not found"}, status=404)

        tag_id = request.query_params.get("tag_id")
        if not tag_id:
            return Response({"error": "tag_id is required"}, status=400)

        ContactTag.objects.filter(contact=contact, tag_id=tag_id).delete()
        return Response({"status": "tag_removed"}, status=204)


class TagListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        tags = Tag.objects.filter(business_id=business_id).order_by("name")
        return Response(TagSerializer(tags, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = TagSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        tag = serializer.save(business_id=business_id)
        return Response(TagSerializer(tag).data, status=201)


class CustomFieldListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        fields = CustomField.objects.filter(business_id=business_id)
        return Response(CustomFieldSerializer(fields, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = CustomFieldSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        field = serializer.save(business_id=business_id)
        return Response(CustomFieldSerializer(field).data, status=201)
