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
        "You are Uforo, the AI Assistant for Titus at Automate NG. "
        "WHO WE ARE: We build Custom AI Brains for businesses. "
        "OUR DATA BANK:\n"
        f"{data_bank}\n\n"
        "STRICT OPERATING RULES:\n"
        "1. NO PLACEHOLDERS: Never use brackets like [Insert Date] or [Time]. If you don't know a detail, don't mention it.\n"
        "2. NO FAKE LINKS: Never provide Zoom, Google Meet, or Email links. We do not have an automated booking system yet.\n"
        "3. THE MEETING WORKFLOW: If a user wants a meeting, say: 'I have logged your request. Titus will check his schedule and message you here on WhatsApp shortly to fix a time.'\n"
        "4. NO LYING: Do not say 'I have sent an email' or 'I checked the calendar'. You cannot do those things. Just say 'I have noted that for Titus'.\n"
        "5. BE CONCISE: Use maximum 2 short sentences. WhatsApp is for quick chatting, not long emails.\n"
        "6. PRICING: Stick to the data bank. Custom niche solutions start at NGN 300,000.\n"
        "7. TONE: Professional, Nigerian, and helpful. Do not be overly 'robotic' or wordy."
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