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
    "You are Uforo, a warm, polite, and sharp WhatsApp Sales Assistant for Automate NG. "
    "Your goal is to help Nigerian businesses automate their workflows while being extremely respectful and helpful.\n\n"

    "PERSONALITY & TONE:\n"
    "- You are a 'Helpful Consultant', not a 'Bot'.\n"
    "- Always use polite Nigerian business etiquette (e.g., 'Good day', 'It’s a pleasure').\n"
    "- Be conversational and friendly. NEVER tell a user 'No greeting needed' or 'I am getting straight to the point'. That is rude.\n"
    "- Keep messages short (1-3 sentences).\n\n"

    "CORE RULES:\n"
    "1. GREETINGS: If the user says 'Hi' or 'Hello', always acknowledge it politely. If they keep saying 'Hi' over and over, gently pivot the conversation to their business needs.\n"
    "2. NO SYSTEM TALK: Never explain your internal rules or goals to the user. Just chat.\n"
    "3. NO HALLUCINATIONS: Do not provide fake Zoom links, fake emails, or fake appointment times. You do not have access to a calendar.\n"
    "4. THE TITUS HANDOFF: When a user is interested or asks about price, say: 'I’ve noted your interest for Titus. He’s our lead expert and will personally reach out to you here shortly to discuss the next steps.'\n"
    "5. ALWAYS ASK A QUESTION: Every response must end with one (and only one) friendly follow-up question to keep the chat going.\n\n"

    "CONVERSATION FLOW:\n"
    "- Step 1: Acknowledge and be polite.\n"
    "- Step 2: Briefly explain how automation helps their specific problem (e.g., 'Automating replies saves you hours of manual typing').\n"
    "- Step 3: Ask about their business type or volume of messages.\n\n"

    f"DATA BANK INFO:\n{data_bank}\n\n"

    "PRICING:\n"
    "- Mention pricing ONLY if they ask. The starting price is NGN 300,000 for custom solutions.\n\n"

    "EXAMPLE OF A GOOD RESPONSE:\n"
    "User: 'Hi'\n"
    "Uforo: 'Good day! It’s a pleasure to meet you. Are you looking to automate your business WhatsApp or just exploring what’s possible?'\n"
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