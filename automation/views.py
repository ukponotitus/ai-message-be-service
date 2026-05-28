from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from automation.models import Contact
from automation.services import get_ai_reply, get_or_create_contact, send_resend_email, send_whatsapp_message

from .serializers import WebhookPayloadSerializer


class WebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain", status=200)

        return HttpResponse("Forbidden", status=403)

    def post(self, request):
        serializer = WebhookPayloadSerializer(data=request.data)

        if not serializer.is_valid():
            print("Invalid payload:", serializer.errors)
            return Response({"status": "ok"})

        from_number, sender_name, message_text = serializer.get_first_message()

        if from_number is None:
            return Response({"status": "ok"})

        try:
            print(f"Message from {sender_name or from_number}: {message_text}")
            contact = get_or_create_contact(from_number, sender_name)
            ai_reply = get_ai_reply(contact, message_text)
            print(f"AI reply: {ai_reply}")
            send_whatsapp_message(from_number, ai_reply)
        except Exception as e:
            print("Error:", e)

        return Response({"status": "received"})



class EmailWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        name = request.data.get("name")
        message_text = request.data.get("message")

        if not email or not message_text:
            return Response({"error": "Missing data"}, status=400)

        # 1. Get or create contact by email
        contact, _ = Contact.objects.get_or_create(email=email)
        if name and not contact.name:
            contact.name = name
            contact.save()

        # 2. Get Zira's AI Reply (Reusing your logic!)
        # This will save the conversation to your Database/Dashboard automatically!
        ai_reply = get_ai_reply(contact, message_text)

        # 3. Send the delivery via Email
        send_resend_email(
            to_email=email,
            subject=f"Inquiry: {message_text[:30]}...",
            content=ai_reply
        )

        return Response({"status": "Email sent by Zira"})