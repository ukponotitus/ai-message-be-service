from django.http import HttpResponse
from django.conf import settings
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny

from automation.models import Contact, Business, ChannelConnection, Conversation, Message, CompanyInfo
from automation.services import get_ai_reply, get_or_create_contact, send_resend_email, send_whatsapp_message
from automation.permissions import HasBusinessAccess, resolve_business_id
from billing.services import can_business_send_message

from .serializers import (
    WebhookPayloadSerializer,
    ChannelConnectionSerializer, ChannelConnectionDetailSerializer,
    ChannelConnectionFrontendSerializer, ChannelConnectionConnectSerializer,
    ContactFrontendSerializer, MessageFrontendSerializer,
    MessageCreateFrontendSerializer, BroadcastFrontendSerializer,
    BroadcastCreateFrontendSerializer, AutomationFrontendSerializer,
    CompanyInfoSerializer, CompanyInfoFrontendSerializer,
    CompanyInfoFrontendCreateSerializer, BusinessOnboardSerializer,
)


class WebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")

        if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge"), content_type="text/plain", status=200)

        return HttpResponse("Forbidden", status=403)

    def post(self, request):
        data = request.data
        
        try:
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            metadata = value.get("metadata", {})
            incoming_phone_id = metadata.get("phone_number_id")
        except (IndexError, KeyError):
            return Response({"status": "invalid payload"}, status=200)

        if not incoming_phone_id:
            return Response({"status": "no phone id"}, status=200)

        business = Business.objects.filter(whatsapp_phone_number_id=incoming_phone_id, is_active=True).first()
        
        if not business:
            print(f"Received message for unknown Phone ID: {incoming_phone_id}")
            return Response({"status": "business not found"}, status=200)

        serializer = WebhookPayloadSerializer(data=data)
        if not serializer.is_valid():
            return Response({"status": "ok"})

        from_number, sender_name, message_text = serializer.get_first_message()
        if not from_number or not message_text:
            return Response({"status": "ok"})

        contact = get_or_create_contact(business, from_number, sender_name)
        
        channel = ChannelConnection.objects.filter(
            business=business, 
            channel_type="whatsapp", 
            phone_number_id=incoming_phone_id
        ).first()

        conversation, _ = Conversation.objects.get_or_create(
            business=business,
            contact=contact,
            channel=channel,
            defaults={"status": "active"},
        )

        if not can_business_send_message(business):
            print(f"Blocking message for {business.name}: No active subscription")
            return Response({"status": "subscription_required"}, status=200)

        if not conversation.is_ai_enabled:
            print(f"AI disabled for conversation {conversation.id}, logging only")
            from .models import AnalyticsEvent
            AnalyticsEvent.objects.create(
                business=business,
                event_type="human_handoff",
                channel=channel,
                contact=contact,
                metadata={"note": "AI disabled, manual reply pending", "message": message_text},
            )
            return Response({"status": "logged_ai_disabled"}, status=200)

        ai_reply = get_ai_reply(business, contact, message_text, conversation, channel)
        
        send_whatsapp_message(business, from_number, ai_reply)

        return Response({"status": "received"})


class EmailWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        business_id = request.data.get("business_id") or request.data.get("business_slug")
        email = request.data.get("email")
        name = request.data.get("name")
        message_text = request.data.get("message")

        if not business_id or not email:
            return Response({"error": "business_id and email are required"}, status=400)

        business = Business.objects.filter(
            Q(id=business_id) | Q(slug=business_id), is_active=True
        ).first()
        if not business:
            return Response({"error": "Invalid or inactive business"}, status=400)

        contact, created = Contact.objects.get_or_create(
            business=business, email=email
        )
        if name and not contact.name:
            contact.name = name
            contact.save(update_fields=["name"])

        ai_reply = get_ai_reply(business, contact, message_text)

        res = send_resend_email(email, f"Re: Inquiry from {name}", ai_reply)
        print(f"Resend Response: {res.status_code} - {res.text}")

        return Response({"status": "Email sent by Zira"})


class BusinessOnboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BusinessOnboardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        business = serializer.save()

        from .auth_views import BusinessMember
        BusinessMember.objects.create(
            user=request.user,
            business=business,
            role="owner",
            is_active=True,
        )

        channels = serializer.validated_data.get("channels", [])
        for ch_type in channels:
            ChannelConnection.objects.get_or_create(
                business=business,
                channel_type=ch_type,
                defaults={"name": ch_type.title(), "status": "active"},
            )

        return Response({"id": business.id, "name": business.name, "slug": business.slug}, status=201)


class BusinessCompanyInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, business_id):
        serializer = CompanyInfoFrontendCreateSerializer(
            data=request.data,
            context={"business_id": business_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        item = serializer.save()
        return Response(CompanyInfoFrontendSerializer(item).data, status=201)


class ChannelListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        channels = ChannelConnection.objects.filter(business_id=business_id).order_by("channel_type")
        return Response(ChannelConnectionFrontendSerializer(channels, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = ChannelConnectionConnectSerializer(
            data=request.data,
            context={"business_id": business_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        channel = serializer.save()
        return Response(ChannelConnectionFrontendSerializer(channel).data, status=201)


class ChannelDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get_object(self, channel_id, business_id):
        return ChannelConnection.objects.filter(id=channel_id, business_id=business_id).first()

    def delete(self, request, channel_id):
        business_id = resolve_business_id(request)
        channel = self.get_object(channel_id, business_id)
        if not channel:
            return Response({"error": "Channel not found"}, status=404)

        channel.is_active = False
        channel.status = "disconnected"
        channel.save(update_fields=["is_active", "status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChannelTestView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, channel_id):
        business_id = resolve_business_id(request)
        channel = ChannelConnection.objects.filter(id=channel_id, business_id=business_id).first()
        if not channel:
            return Response({"error": "Channel not found"}, status=404)

        if channel.channel_type == "whatsapp":
            business = Business.objects.get(id=business_id)
            test_number = request.data.get("test_number", "")
            try:
                resp = send_whatsapp_message(business, test_number, "Test message from your channel connection.")
                success = resp.status_code == 201
                return Response({
                    "success": success,
                    "message": "Test message sent" if success else "Failed to send test message",
                    "status_code": resp.status_code,
                })
            except Exception as e:
                return Response({"success": False, "error": str(e)}, status=500)

        return Response({"success": True, "message": "Channel is configured correctly"})


class MessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        contact_id = request.query_params.get("contact_id")

        qs = Message.objects.filter(business_id=business_id)
        if contact_id:
            qs = qs.filter(contact_id=contact_id)

        qs = qs.order_by("-created_at")[:100]
        return Response(MessageFrontendSerializer(qs, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = MessageCreateFrontendSerializer(
            data=request.data,
            context={"business_id": business_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        msg = serializer.save()
        return Response(MessageFrontendSerializer(msg).data, status=201)


class CompanyInfoListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        items = CompanyInfo.objects.filter(business_id=business_id).order_by("key")
        return Response(CompanyInfoFrontendSerializer(items, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = CompanyInfoFrontendCreateSerializer(
            data=request.data,
            context={"business_id": business_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        item = serializer.save()
        return Response(CompanyInfoFrontendSerializer(item).data, status=201)


class CompanyInfoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get_object(self, info_id, business_id):
        return CompanyInfo.objects.filter(id=info_id, business_id=business_id).first()

    def patch(self, request, info_id):
        business_id = resolve_business_id(request)
        obj = self.get_object(info_id, business_id)
        if not obj:
            return Response({"error": "Company info not found"}, status=404)

        if "question" in request.data:
            obj.key = request.data["question"]
        if "answer" in request.data:
            obj.content = request.data["answer"]
        obj.save()

        return Response(CompanyInfoFrontendSerializer(obj).data)

    def delete(self, request, info_id):
        business_id = resolve_business_id(request)
        obj = self.get_object(info_id, business_id)
        if not obj:
            return Response({"error": "Company info not found"}, status=404)

        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
