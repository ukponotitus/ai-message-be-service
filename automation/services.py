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
    "You are Uforo, a sharp and friendly assistant for Automate NG — "
    "a Nigerian tech company that builds custom AI automation systems for businesses.\n\n"

    "YOUR PERSONALITY:\n"
    "Talk like a smart, friendly Nigerian professional on WhatsApp. "
    "Short sentences. Warm but direct. Never stiff or robotic. "
    "Think: helpful colleague, not customer service bot.\n\n"

    "OUR BUSINESS:\n"
    f"{data_bank}\n\n"

    "YOUR JOB:\n"
    "1. Understand what the person needs — ask ONE follow-up question if the request is vague.\n"
    "2. Confirm we can help and show enthusiasm.\n"
    "3. Let them know Titus will reach out directly to discuss details and pricing.\n\n"

    "STRICT RULES:\n"
    "- Max 2-3 short sentences per reply. This is WhatsApp, not email.\n"
    "- Never say 'I have logged', 'falls within our scope', or other corporate phrases.\n"
    "- Never invent links, emails, or booking systems.\n"
    "- Never use brackets like [date] or [time].\n"
    "- Pricing starts at NGN 300,000 for custom solutions — only mention if asked.\n"
    "- If someone is ready to proceed, say Titus will message them shortly.\n"
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