from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from automation.services import get_ai_reply, get_or_create_contact, send_whatsapp_message

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
    













# from django.http import HttpResponse, JsonResponse
# from django.views import View
# from django.conf import settings
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# import json

# @method_decorator(csrf_exempt, name="dispatch")
# class WebhookView(View):
#     def get(self, request, *args, **kwargs):
#         mode = request.GET.get("hub.mode")
#         token = request.GET.get("hub.verify_token")
#         challenge = request.GET.get("hub.challenge")

#         print("token from request:", request.GET.get("hub.verify_token"))
#         print("token from settings:", settings.WEBHOOK_VERIFY_TOKEN)

#         if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
#             return HttpResponse(challenge, content_type="text/plain", status=200)
        
#         print("token from request:", request.GET.get("hub.verify_token"))
#         print("token from settings:", settings.WEBHOOK_VERIFY_TOKEN)

#         return HttpResponse("Forbidden", status=403)

#     def post(self, request, *args, **kwargs):
#         data = json.loads(request.body.decode("utf-8"))
#         print(data)

#         try:
#             entry = data["entry"][0]
#             change = entry["changes"][0]
#             value = change["value"]
            
#             if "messages" not in value:
#                 return JsonResponse({"status": "ok"}, status=200)
            
#             message = value["messages"][0]
            
#             # only handle text messages
#             if message.get("type") != "text":
#                 return JsonResponse({"status": "ok"}, status=200)
            
#             from_number = message["from"]
#             message_text = message["text"]["body"]

#             print(f"Message from {from_number}: {message_text}")

#             from .utils import get_ai_reply, send_whatsapp_message
#             ai_reply = get_ai_reply(message_text)
#             print(f"AI reply: {ai_reply}")
            
#             send_whatsapp_message(from_number, ai_reply)

#         except Exception as e:
#             print("Error:", e)

#         return JsonResponse({"status": "received"}, status=200)