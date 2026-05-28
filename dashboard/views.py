from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta
from automation.models import Message, Contact
from django.db.models import Max
from django.db.models import Q



class DashboardMetricsAPI(APIView):
    def get(self, request):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        msg_today = Message.objects.filter(created_at__date=today).count()
        msg_yesterday = Message.objects.filter(created_at__date=yesterday).count()
        
        avg_res = Message.objects.filter(role="assistant").aggregate(Avg('response_time'))['response_time__avg'] or 0
        
        return Response({
            "messages_today": msg_today,
            "diff_yesterday": msg_today - msg_yesterday,
            "unique_contacts": Contact.objects.filter(created_at__date__gte=today-timedelta(days=7)).count(),
            "avg_response": f"{round(avg_res, 1)}s"
        })
    

class DashboardAnalyticsAPI(APIView):
    def get(self, request):
        status_data = Message.objects.filter(role="assistant").values('status').annotate(count=Count('id'))
        
        keywords = ["Pricing", "How it works", "Setup", "Link", "Custom"]
        top_questions = []
        for word in keywords:
            count = Message.objects.filter(role="user", content__icontains=word).count()
            top_questions.append({"label": word, "count": count})

        return Response({
            "status_breakdown": {item['status']: item['count'] for item in status_data},
            "top_questions": top_questions
        })


class DashboardLogsAPI(APIView):
    def get(self, request):
        recent_contacts = Contact.objects.annotate(
            last_msg_time=Max('messages__created_at')
        ).filter(last_msg_time__isnull=False).order_by('-last_msg_time')[:10]

        logs = []

        for contact in recent_contacts:
            latest_user_msg = Message.objects.filter(
                contact=contact, 
                role="user"
            ).order_by('-created_at').first()

            latest_ai_reply = Message.objects.filter(
                contact=contact, 
                role="assistant"
            ).order_by('-created_at').first()

            if latest_user_msg:
                logs.append({
                    "name": contact.name or "Unknown",
                    "phone": contact.phone,
                    "message": latest_user_msg.content,
                    "ai_reply": latest_ai_reply.content if latest_ai_reply else "Waiting for response...",
                    "time": latest_user_msg.created_at.strftime("%I:%M %p"),
                    "status": latest_ai_reply.status if latest_ai_reply else "pending"
                })

        return Response(logs)
    

class ConversationDetailAPI(APIView):
    def get(self, request, phone, identifier):
        # messages = Message.objects.filter(contact__phone=phone).order_by('created_at')
        messages = Message.objects.filter(
            Q(contact__phone=identifier) | Q(contact__email=identifier)
        ).order_at('created_at')
        serializer_data = [ 
            {
                "role": m.role,
                "content": m.content,
                "time": m.created_at.strftime("%I:%M %p")
            } for m in messages
        ]
        return Response(serializer_data)