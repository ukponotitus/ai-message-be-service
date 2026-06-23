from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone

from .models import AutomationFlow, Broadcast, BroadcastRecipient, Contact, ChannelConnection, Business
from .permissions import HasBusinessAccess, resolve_business_id
from billing.services import check_automation_limit
from .serializers import (
    AutomationFlowSerializer, AutomationFrontendSerializer,
    BroadcastSerializer, BroadcastDetailSerializer,
    BroadcastFrontendSerializer, BroadcastCreateFrontendSerializer,
    BroadcastUpdateFrontendSerializer,
)


class AutomationListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        automations = AutomationFlow.objects.filter(business_id=business_id).order_by("-created_at")
        return Response(AutomationFrontendSerializer(automations, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        business = Business.objects.get(id=business_id)
        ok, used, limit = check_automation_limit(business)
        if not ok:
            return Response({"error": f"Automation limit reached ({used}/{limit}). Upgrade your plan to create more automations."}, status=400)

        data = {**request.data}
        if "trigger" in data and data["trigger"] not in dict(AutomationFlow.TRIGGER_CHOICES):
            data["trigger"] = "message_received"
        serializer = AutomationFlowSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        automation = serializer.save(business_id=business_id)
        return Response(AutomationFrontendSerializer(automation).data, status=201)


class AutomationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get_object(self, automation_id, business_id):
        return AutomationFlow.objects.filter(id=automation_id, business_id=business_id).first()

    def get(self, request, automation_id):
        business_id = resolve_business_id(request)
        automation = self.get_object(automation_id, business_id)
        if not automation:
            return Response({"error": "Automation not found"}, status=404)
        return Response(AutomationFrontendSerializer(automation).data)

    def patch(self, request, automation_id):
        business_id = resolve_business_id(request)
        automation = self.get_object(automation_id, business_id)
        if not automation:
            return Response({"error": "Automation not found"}, status=404)

        data = {**request.data}
        if "is_active" in data:
            automation.is_active = data["is_active"]
            automation.save(update_fields=["is_active"])

        if "name" in data:
            automation.name = data["name"]
            automation.save(update_fields=["name"])

        return Response(AutomationFrontendSerializer(automation).data)

    def delete(self, request, automation_id):
        business_id = resolve_business_id(request)
        automation = self.get_object(automation_id, business_id)
        if not automation:
            return Response({"error": "Automation not found"}, status=404)

        automation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AutomationPublishView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, automation_id):
        business_id = resolve_business_id(request)
        automation = AutomationFlow.objects.filter(id=automation_id, business_id=business_id).first()
        if not automation:
            return Response({"error": "Automation not found"}, status=404)

        automation.is_active = True
        automation.published_at = timezone.now()
        automation.save(update_fields=["is_active", "published_at"])

        return Response(AutomationFrontendSerializer(automation).data)


class BroadcastListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        broadcasts = Broadcast.objects.filter(business_id=business_id).select_related("channel").order_by("-created_at")
        return Response(BroadcastFrontendSerializer(broadcasts, many=True).data)

    def post(self, request):
        business_id = resolve_business_id(request)
        serializer = BroadcastCreateFrontendSerializer(
            data=request.data,
            context={"business_id": business_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        broadcast = serializer.save()
        return Response(BroadcastFrontendSerializer(broadcast).data, status=201)


class BroadcastDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get_object(self, broadcast_id, business_id):
        return Broadcast.objects.filter(id=broadcast_id, business_id=business_id).first()

    def get(self, request, broadcast_id):
        business_id = resolve_business_id(request)
        broadcast = self.get_object(broadcast_id, business_id)
        if not broadcast:
            return Response({"error": "Broadcast not found"}, status=404)
        return Response(BroadcastDetailSerializer(broadcast).data)

    def patch(self, request, broadcast_id):
        business_id = resolve_business_id(request)
        broadcast = self.get_object(broadcast_id, business_id)
        if not broadcast:
            return Response({"error": "Broadcast not found"}, status=404)

        if broadcast.status != "draft":
            return Response({"error": "Only draft broadcasts can be edited."}, status=400)

        data = {**request.data}
        updatable = ["name", "message_content", "email_subject", "channel_type", "scheduled_at"]
        fields_to_save = []
        for field in updatable:
            if field in data:
                setattr(broadcast, field, data[field])
                fields_to_save.append(field)

        if "channel" in data and data["channel"] != broadcast.channel_type:
            broadcast.channel_type = data["channel"]
            fields_to_save.append("channel_type")

        if "status" in data:
            broadcast.status = data["status"]
            fields_to_save.append("status")

        if "content" in data:
            broadcast.message_content = data["content"]
            fields_to_save.append("message_content")

        if fields_to_save:
            broadcast.save(update_fields=fields_to_save)

        if "contact_ids" in data:
            broadcast.contacts.set(data["contact_ids"])

        return Response(BroadcastFrontendSerializer(broadcast).data)

    def delete(self, request, broadcast_id):
        business_id = resolve_business_id(request)
        broadcast = self.get_object(broadcast_id, business_id)
        if not broadcast:
            return Response({"error": "Broadcast not found"}, status=404)

        if broadcast.status != "draft":
            return Response({"error": "Only draft broadcasts can be deleted."}, status=400)

        broadcast.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BroadcastScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, broadcast_id):
        business_id = resolve_business_id(request)
        broadcast = Broadcast.objects.filter(id=broadcast_id, business_id=business_id).first()
        if not broadcast:
            return Response({"error": "Broadcast not found"}, status=404)

        scheduled_at = request.data.get("scheduled_at")
        if not scheduled_at:
            return Response({"error": "scheduled_at is required"}, status=400)

        broadcast.scheduled_at = scheduled_at
        broadcast.status = "scheduled"
        broadcast.save(update_fields=["scheduled_at", "status"])

        return Response(BroadcastSerializer(broadcast).data)


class BroadcastSendView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def post(self, request, broadcast_id):
        business_id = resolve_business_id(request)
        broadcast = Broadcast.objects.filter(id=broadcast_id, business_id=business_id).first()
        if not broadcast:
            return Response({"error": "Broadcast not found"}, status=404)

        business = Business.objects.get(id=business_id)
        channel = broadcast.channel
        channel_type = broadcast.channel_type or (channel.channel_type if channel else "")
        contacts = Contact.objects.filter(business_id=business_id)

        contact_ids = request.data.get("contact_ids", None)
        if contact_ids is not None:
            contacts = contacts.filter(id__in=contact_ids)
        else:
            stored_ids = broadcast.contacts.values_list("id", flat=True)
            if stored_ids:
                contacts = contacts.filter(id__in=stored_ids)

        broadcast.status = "sending"
        broadcast.total_count = contacts.count()
        broadcast.save(update_fields=["status", "total_count"])

        sent = 0
        failed = 0

        if channel_type == "email":
            from .services import send_resend_email
            subject = broadcast.email_subject or "New message from " + business.name

            for contact in contacts:
                if not contact.email:
                    failed += 1
                    continue
                try:
                    send_resend_email(contact.email, subject, broadcast.message_content)
                    BroadcastRecipient.objects.create(
                        broadcast=broadcast,
                        contact=contact,
                        status="sent",
                        sent_at=timezone.now(),
                    )
                    sent += 1
                except Exception as e:
                    BroadcastRecipient.objects.create(
                        broadcast=broadcast,
                        contact=contact,
                        status="failed",
                        error_message=str(e),
                    )
                    failed += 1
        else:
            if channel_type == "whatsapp":
                from .services import send_whatsapp_message

                for contact in contacts:
                    if not contact.phone:
                        failed += 1
                        continue
                    try:
                        send_whatsapp_message(business, contact.phone, broadcast.message_content)
                        BroadcastRecipient.objects.create(
                            broadcast=broadcast,
                            contact=contact,
                            status="sent",
                            sent_at=timezone.now(),
                        )
                        sent += 1
                    except Exception as e:
                        BroadcastRecipient.objects.create(
                            broadcast=broadcast,
                            contact=contact,
                            status="failed",
                            error_message=str(e),
                        )
                        failed += 1
            else:
                failed = contacts.count()

        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.status = "sent"
        broadcast.save(update_fields=["sent_count", "failed_count", "status"])

        return Response(BroadcastFrontendSerializer(broadcast).data)
