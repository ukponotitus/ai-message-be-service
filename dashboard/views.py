from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Max, Q
from django.utils import timezone
from datetime import timedelta
from automation.models import Message, Contact
from automation.permissions import HasBusinessAccess, resolve_business_id



class DashboardMetricsAPI(APIView):
    permission_classes = [IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        if not business_id:
            return Response({"error": "business_id is required"}, status=400)

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        msg_today = Message.objects.filter(business_id=business_id, created_at__date=today).count()
        msg_yesterday = Message.objects.filter(business_id=business_id, created_at__date=yesterday).count()
        
        avg_res = Message.objects.filter(business_id=business_id, role="assistant").aggregate(Avg('response_time'))['response_time__avg'] or 0
        
        return Response({
            "messages_today": msg_today,
            "diff_yesterday": msg_today - msg_yesterday,
            "unique_contacts": Contact.objects.filter(business_id=business_id, created_at__date__gte=today-timedelta(days=7)).count(),
            "avg_response": f"{round(avg_res, 1)}s"
        })
    

class DashboardAnalyticsAPI(APIView):
    permission_classes = [IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        if not business_id:
            return Response({"error": "business_id is required"}, status=400)

        status_data = Message.objects.filter(business_id=business_id, role="assistant").values('status').annotate(count=Count('id'))
        
        keywords = ["Pricing", "How it works", "Setup", "Link", "Custom"]
        top_questions = []
        for word in keywords:
            count = Message.objects.filter(business_id=business_id, role="user", content__icontains=word).count()
            top_questions.append({"label": word, "count": count})

        return Response({
            "status_breakdown": {item['status']: item['count'] for item in status_data},
            "top_questions": top_questions
        })


class DashboardLogsAPI(APIView):
    permission_classes = [IsAuthenticated, HasBusinessAccess]

    def get(self, request):
        business_id = resolve_business_id(request)
        if not business_id:
            return Response({"error": "business_id is required"}, status=400)

        recent_contacts = Contact.objects.filter(business_id=business_id).annotate(
            last_msg_time=Max('messages__created_at')
        ).filter(last_msg_time__isnull=False).order_by('-last_msg_time')[:10]

        logs = []

        for contact in recent_contacts:
            latest_user_msg = Message.objects.filter(
                business_id=business_id,
                contact=contact, 
                role="user"
            ).order_by('-created_at').first()

            latest_ai_reply = Message.objects.filter(
                business_id=business_id,
                contact=contact, 
                role="assistant"
            ).order_by('-created_at').first()

            if latest_user_msg:
                logs.append({
                    "name": contact.name or "Unknown",
                    "phone": contact.phone,
                    "email": contact.email, 
                    "message": latest_user_msg.content,
                    "ai_reply": latest_ai_reply.content if latest_ai_reply else "Waiting...",
                    "time": latest_user_msg.created_at.strftime("%I:%M %p"),
                    "status": latest_ai_reply.status if latest_ai_reply else "sent"
                })
        return Response(logs)
    

from django.db.models import Q

class ConversationDetailAPI(APIView):
    permission_classes = [IsAuthenticated, HasBusinessAccess]

    def get(self, request, identifier):
        business_id = resolve_business_id(request)
        if not business_id:
            return Response({"error": "business_id is required"}, status=400)

        messages = Message.objects.filter(
            business_id=business_id,
            contact__in=Contact.objects.filter(
                Q(phone=identifier) | 
                Q(email=identifier) |
                Q(name=identifier)
            )
        ).order_by('created_at')

        serializer_data = [ 
            {
                "role": m.role,
                "content": m.content,
                "time": m.created_at.strftime("%I:%M %p")
            } for m in messages
        ]
        return Response(serializer_data)