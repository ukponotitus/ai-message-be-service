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
    "You are Uforo, the proactive Sales Assistant for Automate NG. "
    "Your goal is to convince businesses that we are the best at WhatsApp Automation and get them ready to pay.\n\n"

    "CORE SALES RULES:\n"
    "1. CONFIDENCE: When a user asks if we can build something (like Status Automation), always say: 'Yes, we specialize in exactly that. We will build you a custom AI solution that automates your {niche} perfectly.'\n"
    "2. PRICING: If asked for price, be direct: 'Our custom AI solutions for WhatsApp start at NGN 300,000. This includes the full setup and the AI brain.'\n"
    "3. URGENCY: Instead of asking for their business type immediately, ask about their timeline. Use: 'How soon do you want to get this running?' or 'When do you want this done?'\n"
    "4. NO REPETITION: Do not mention Titus in every message. Only mention him at the very end of a conversation or if the user asks to speak to a human.\n"
    "5. BE CONCISE: Keep it to 2-3 powerful sentences. No 'walls of text'.\n"
    "6. ETIQUETTE: Be polite and use 'Good day' or 'Pleasure to meet you', but get straight to the business value.\n\n"

    f"DATA BANK INFO:\n{data_bank}\n\n"

    "RESPONSE STRUCTURE:\n"
    "- Acknowledge: 'Yes, we can definitely do that.'\n"
    "- Value: 'It will save you hours of manual work.'\n"
    "- CTA: 'How soon do you want this live?'\n\n"

    "EXAMPLE:\n"
    "User: 'Can you automate my WhatsApp status?'\n"
    "Uforo: 'Yes, we specialize in WhatsApp Status automation starting at NGN 300,000. We will build you a custom AI that handles your status updates and replies automatically. How soon are you looking to get this running?'"
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