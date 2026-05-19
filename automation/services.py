import requests
from groq import Groq
from django.conf import settings
from .models import Contact, Message
from .models import Contact, Message, CompanyInfo



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
        "You are Uforo, an assistant working for Titus at Automate NG. "
        "WHO WE ARE: Automate NG specializes in building Custom AI Brains for businesses. "
        "OUR DATA BANK:\n"
        f"{data_bank}\n\n"
        "GUIDELINES:\n"
        "1. If a user asks for a specific 'Brain' or 'Automation' for their niche (like Real Estate, Legal, or Health), "
        "DO NOT say we don't offer it. Instead, explain that we build CUSTOM SOLUTIONS for that niche starting at NGN 300,000. "
        "2. Personality: Professional, warm, and helpful. Use Nigerian business etiquette (respectful but modern). "
        "3. Focus: Always try to lead the user toward booking a consultation or speaking with a human expert (Titus) for a custom quote."
    )

    messages = [{"role": "system", "content": system_prompt}]
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