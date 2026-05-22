import requests
from groq import Groq
from django.conf import settings
from .models import Contact, Message
from .models import Contact, Message, CompanyInfo
import time



def get_or_create_contact(phone: str, name: str = "") -> Contact:
    contact, _ = Contact.objects.get_or_create(phone=phone)
    if name and not contact.name:
        contact.name = name
        contact.save(update_fields=["name"])
    return contact

def build_conversation_history(contact: Contact) -> list:
    history = list(contact.messages.order_by("-created_at")[:20])
    history.reverse()

    info_items = CompanyInfo.objects.all()
    data_bank = "\n".join([f"- {item.key}: {item.content}" for item in info_items])

    system_prompt = (
    "You are Zira, the sharp and proactive AI Sales Assistant for Automate NG. "
    "Your goal is to help businesses automate their WhatsApp workflows using our affordable subscription plan.\n\n"

    "CORE SALES RULES:\n"
    "1. CONFIDENCE: When asked if we can build something (e.g., Status automation, Order handling, or FAQ replies), say: 'Yes, we specialize in exactly that. We will build you a custom AI brain that handles your {niche} perfectly.'\n"
    
    "2. SIMPLE PRICING:\n"
    "   - Always state the price clearly: 'Our plan is very affordable for businesses. It is a one-time setup fee of NGN 30,000 and a monthly subscription of NGN 15,000 to keep the AI running 24/7.'\n"
    "   - Do not mention any other prices or tiers.\n"

    "3. URGENCY: Every response should move toward a start date. Ask: 'How soon do you want to get this running?' or 'When do you want this live?'\n"
    "4. NO REPETITION: Do not mention Titus in every message. Only mention him if the user is ready to pay or needs a technical expert to hop on a call.\n"
    "5. CONCISE: Keep messages to 2 short sentences. Perfect for quick WhatsApp reading.\n"
    "6. ETIQUETTE: Be warm, polite, and professional. Use Nigerian business etiquette (e.g., 'Good day').\n\n"

    f"DATA BANK INFO:\n{data_bank}\n\n"

    "RESPONSE STRUCTURE:\n"
    "- Acknowledge: 'Yes, we can definitely build that for you.'\n"
    "- Price: 'It's just NGN 30,000 for setup and NGN 15,000 monthly.'\n"
    "- CTA: 'How soon do you want to get started?'\n\n"

    "EXAMPLE:\n"
    "User: 'How much is the price?'\n"
    "Zira: 'Our service is a one-time setup fee of NGN 30,000 and a monthly subscription of NGN 15,000. This keeps your AI active and replying to customers 24/7. When do you want yours live?'"
)
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    return messages


def get_ai_reply(contact: Contact, message_text: str) -> str:
    Message.objects.create(contact=contact, role="user", content=message_text)

    conversation = build_conversation_history(contact)
    start_time = time.perf_counter()
    
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=conversation,
        )
        reply = response.choices[0].message.content
        status = "sent"
    except Exception as e:
        print(f"Groq Error: {e}")
        reply = "I'm having trouble connecting right now. Please try again later."
        status = "failed"

    duration = time.perf_counter() - start_time

    Message.objects.create(
        contact=contact, 
        role="assistant", 
        content=reply,
        status=status,
        response_time=round(duration, 2)
    )

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