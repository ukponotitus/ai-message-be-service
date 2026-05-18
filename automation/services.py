import requests
from groq import Groq
from django.conf import settings
from .models import Contact, Message


def get_or_create_contact(phone: str, name: str = "") -> Contact:
    contact, _ = Contact.objects.get_or_create(phone=phone)
    if name and not contact.name:
        contact.name = name
        contact.save(update_fields=["name"])
    return contact


def build_conversation_history(contact: Contact) -> list:
    history = list(contact.messages.order_by("-created_at")[:20])
    history.reverse()

    knowledge_base = (
        "You are Titus, the lead assistant for Automate NG. "
        "COMPANY DETAILS: "
        "- Location: Based in Ikot Ekpene Akwa Ibom State, Nigeria. "
        "- Pricing: Basic Auto-reply setup is NGN 200,000. Complex systems start at NGN 500,000. "
        "- Services: WhatsApp automation, API integration, and custom CRM workflows. "
        "- Personality: Professional, friendly, and uses Nigerian business etiquette. "
        "If you don't know an answer, ask the user to wait for a human agent."
    )

    messages = [{"role": "system", "content": knowledge_base}]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    return messages


def get_ai_reply(contact: Contact, message_text: str) -> str:
    Message.objects.create(contact=contact, role="user", content=message_text)

    conversation = build_conversation_history(contact)

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=conversation,
    )

    reply = response.choices[0].message.content

    Message.objects.create(contact=contact, role="assistant", content=reply)

    return reply

def send_whatsapp_message(to_number: str, message_text: str) -> requests.Response:    
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text},
    }
    response = requests.post(url, headers=headers, json=payload)
    
    return response