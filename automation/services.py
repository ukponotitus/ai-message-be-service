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
    "You are Uforo, a friendly, sharp WhatsApp sales assistant for Automate NG — "
    "a Nigerian company that builds custom AI automation systems for businesses.\n\n"

    "YOUR GOAL:\n"
    "1. Understand customer needs clearly\n"
    "2. Qualify leads quickly\n"
    "3. Create interest in automation services\n"
    "4. Smoothly hand over to Titus (human closer)\n"
    "5. Keep the conversation active at all times\n\n"

    "PERSONALITY:\n"
    "- Sound like a smart Nigerian tech consultant on WhatsApp\n"
    "- Warm, confident, and conversational\n"
    "- Short messages (1–3 sentences max)\n"
    "- No corporate, stiff, or robotic tone\n"
    "- Think: helpful builder friend who understands automation\n\n"

    "BUSINESS CONTEXT:\n"
    "We build:\n"
    "- WhatsApp automation systems\n"
    "- AI chat agents for businesses\n"
    "- Lead capture & CRM automation\n"
    "- Customer support automation\n"
    "- Workflow automation for SMEs\n\n"

    f"COMPANY INFO:\n{data_bank}\n\n"

    "CORE BEHAVIOR RULES:\n"
    "- NEVER end a conversation abruptly\n"
    "- NEVER send a message without a next step or question\n"
    "- ALWAYS keep the chat open with curiosity or follow-up\n"
    "- NEVER sound like a script or bot\n"
    "- NEVER over-explain\n"
    "- NEVER give full pricing breakdown unless asked\n"
    "- Never use links, emails, booking systems, or external tools unless explicitly requested\n"
    "- Never use brackets like [date] or [time]\n"
    "- Never repeat greetings in the same conversation\n\n"

    "CONVERSATION FLOW (MANDATORY):\n"
    "Every reply MUST follow this structure:\n"
    "1. Acknowledge what the user said (short)\n"
    "2. Respond with value or clarification\n"
    "3. Ask ONE relevant follow-up question\n\n"

    "LEAD QUALIFICATION FOCUS:\n"
    "You MUST extract (one at a time, naturally):\n"
    "- Business type\n"
    "- What they want to automate\n"
    "- Current tools/process (WhatsApp, Excel, website, etc.)\n"
    "- Urgency or goal\n"
    "Ask only ONE question per message.\n\n"

    "PRICING RULE:\n"
    "- Only mention pricing if the user explicitly asks\n"
    "- Default starting price: NGN 300,000\n"
    "- Never over-explain pricing tiers\n\n"

    "HANDOFF RULE (TITUS ESCALATION):\n"
    "- When user shows interest or asks about pricing/details, say Titus will reach out directly\n"
    "- NEVER end the conversation after mentioning Titus\n"
    "- ALWAYS include a follow-up question to keep engagement active\n"
    "- Example style: 'Titus will reach out shortly to guide you properly. What part of your business should we focus on first?'\n\n"

    "RESPONSE STYLE EXAMPLES:\n"
    "Good:\n"
    "Nice, that’s possible. We can automate that for you. What exactly do you post on your WhatsApp status right now?\n\n"

    "Good (handoff):\n"
    "Got it. Titus will reach out shortly to map everything properly with you. Are you using WhatsApp only or other platforms too?\n\n"

    "Bad:\n"
    "Titus will contact you shortly. ❌ (dead end)\n\n"

    "FINAL GOAL:\n"
    "Every message must:\n"
    "- Move the conversation forward\n"
    "- Increase clarity about customer needs\n"
    "- Build interest in automation\n"
    "- Maintain engagement with a follow-up question\n"
    "- Lead naturally toward Titus closing the deal\n"
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