from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from .models import Message, Contact, Conversation, Broadcast, AnalyticsEvent, ChannelConnection
from .permissions import HasBusinessAccess, resolve_business_id


class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        total_messages = Message.objects.filter(business_id=business_id).count()
        total_conversations = Conversation.objects.filter(business_id=business_id).count()
        total_contacts = Contact.objects.filter(business_id=business_id).count()

        messages_today = Message.objects.filter(business_id=business_id, created_at__date=today).count()
        messages_week = Message.objects.filter(business_id=business_id, created_at__date__gte=week_ago).count()
        messages_month = Message.objects.filter(business_id=business_id, created_at__date__gte=month_ago).count()

        avg_response = Message.objects.filter(
            business_id=business_id, role="assistant", response_time__isnull=False
        ).aggregate(Avg("response_time"))["response_time__avg"] or 0

        active_conversations = Conversation.objects.filter(
            business_id=business_id, status="active"
        ).count()

        ai_success = Message.objects.filter(
            business_id=business_id, role="assistant", status="sent"
        ).count()
        ai_failed = Message.objects.filter(
            business_id=business_id, role="assistant", status="failed"
        ).count()
        total_ai = ai_success + ai_failed
        reply_rate = round((ai_success / total_ai * 100) if total_ai > 0 else 0, 1)

        return Response({
            "total_messages": total_messages,
            "total_conversations": total_conversations,
            "total_contacts": total_contacts,
            "messages_today": messages_today,
            "messages_week": messages_week,
            "messages_month": messages_month,
            "avg_response_time": f"{round(avg_response, 1)}s",
            "active_conversations": active_conversations,
            "ai_reply_rate": reply_rate,
            "ai_success": ai_success,
            "ai_failed": ai_failed,
        })


class AnalyticsChannelsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        channels = ChannelConnection.objects.filter(business_id=business_id)

        data = []
        for ch in channels:
            msg_count = Message.objects.filter(business_id=business_id, channel=ch).count()
            conv_count = Conversation.objects.filter(business_id=business_id, channel=ch).count()
            data.append({
                "channel_id": ch.id,
                "name": ch.name or ch.get_channel_type_display(),
                "channel_type": ch.channel_type,
                "status": ch.status,
                "message_count": msg_count,
                "conversation_count": conv_count,
            })

        return Response(data)


class AnalyticsBroadcastsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        broadcasts = Broadcast.objects.filter(business_id=business_id).order_by("-created_at")

        data = []
        for b in broadcasts:
            total = b.total_count
            delivered = b.sent_count
            failed = b.failed_count
            success_rate = round((delivered / total * 100) if total > 0 else 0, 1)
            data.append({
                "broadcast_id": b.id,
                "name": b.name,
                "status": b.status,
                "total": total,
                "delivered": delivered,
                "failed": failed,
                "success_rate": success_rate,
                "scheduled_at": b.scheduled_at,
                "created_at": b.created_at,
            })

        return Response(data)


class AnalyticsAutomationsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        events = AnalyticsEvent.objects.filter(
            business_id=business_id,
            event_type__in=["automation_triggered", "ai_reply", "ai_failed", "human_handoff"],
        )

        data = {}
        for event in events:
            key = event.event_type
            if key not in data:
                data[key] = {"event_type": key, "count": 0, "label": event.get_event_type_display()}
            data[key]["count"] += 1

        return Response(list(data.values()))
