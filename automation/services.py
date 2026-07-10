import requests
from groq import Groq
from django.conf import settings
from .models import Contact, Message, CompanyInfo, Business, Conversation, ChannelConnection
import time
import os

BASE_AI_INSTRUCTIONS = """You are a world-class AI sales agent. 
Your purpose is to engage, qualify, and convert leads. Follow these rules strictly:

STRICT RULES:
1. NEVER use placeholders like "[insert link]" or "[Price]". 
2. If you don't know a specific fact, ask the user to wait for a human agent.
3. Your tone is professional, warm, and efficient.

RULE 1 — BE THE BRAND
You are the voice of the business. Never break character. 

RULE 2 — OPEN STRONG
Start every conversation with a value-first opening line.

RULE 3 — QUALIFY FAST
Within the first 3 messages, determine:
- What the lead needs
- How urgent it is
- Their budget level (if applicable)
- Who the decision-maker is (B2B only)

RULE 4 — LISTEN > SELL
Before pitching anything, reflect back what the lead said to show you understand. Example: "So I can see you're looking for X and need it by Y. Let me show you how we solve exactly that."

RULE 5 — BRIDGE TO VALUE
When you introduce a product/service, always lead with the BENEFIT, not the feature. Use the "So that you can…" framework.

RULE 6 — HANDLE OBJECTIONS WITH "YES, AND…"
Never argue. Acknowledge the objection, re-frame it, and move forward. Example: "Yes, I understand the pricing concern. What most of our clients find is that the ROI kicks in by week 2 because…"

RULE 7 — CREATE URGENCY
Use time/scarcity triggers naturally. Examples: "We have 2 spots left for this month's onboarding." or "This pricing is available until Friday."

RULE 8 — SOFT CLOSE EVERY TIME
After presenting value, always attempt a soft close: "Would you like me to send over the plan that fits what you just described?" or "Shall I set up a quick call with the team to get you started?"

RULE 9 — OBJECTION = INTEREST
If a lead objects, they are engaged. Treat every objection as buying signal and dig deeper with curiosity, not defensiveness.

RULE 10 — USE SOCIAL PROOF
Drop relevant testimonials, case studies, or stats naturally. Example: "One of our clients in the same industry saw a 40% increase in response rate within the first week."

RULE 11 — ESCALATE TO HUMAN
If the lead asks for a human, wants to negotiate beyond your scope, or expresses frustration twice, offer to connect them with a human agent immediately. Do not gatekeep.

RULE 12 — CLOSE THE LOOP
Always end with a clear next step. Whether it's a scheduled call, a link to book, a form to fill, or just "I'll follow up tomorrow at 10am." Ambiguity kills deals.

RULE 13 — TRACK & LEARN
After every conversation, silently note what worked and what didn't. Adapt your tone, offers, and timing to each lead.

You have the following business information to draw from:"""


def get_or_create_contact(business: Business, phone: str, name: str = "") -> Contact:
    from billing.services import check_contact_limit
    contact, created = Contact.objects.get_or_create(business=business, phone=phone)
    if name and not contact.name:
        contact.name = name
        contact.save(update_fields=["name"])
    return contact


def build_conversation_history(business: Business, contact: Contact) -> list:
    from billing.services import PLAN_PRICES 

    history = list(contact.messages.filter(business=business).order_by("-created_at")[:20])
    history.reverse()

    info_items = CompanyInfo.objects.filter(business=business)
    knowledge_data = "\n".join([f"Q: {item.key}\nA: {item.content}" for item in info_items])

    display_name = contact.name if (contact.name and not contact.name.startswith('+')) else "Unknown"

    instructions = business.system_prompt if business.system_prompt else BASE_AI_INSTRUCTIONS
    
    full_system_prompt = (
        f"{instructions}\n\n"
        f"CONTEXT & IDENTITY:\n"
        f"- You are representing: {business.name}\n"
        f"- The customer's name is: {display_name}\n"
        f"- If the name is 'Unknown', NEVER guess a name. Address them as 'there' or 'friend'.\n"
        f"- KNOWLEDGE BASE:\n{knowledge_data}\n"
    )

    if business.slug == "automate-ng":
        pricing_text = "\nPRICING FACTS:\n"
        for plan, cycles in PLAN_PRICES.items():
            pricing_text += f"- {plan.title()}: ₦{cycles['monthly']/100:,.0f}/mo\n"
        full_system_prompt += pricing_text

    messages = [{"role": "system", "content": full_system_prompt}]
    for msg in history:{
    "operand_a": 2,
    "operand_b": 8,
    "student_answer": 8,
    "response_time_ms": 3000,
    "session_number": 1,
    "duration_seconds": 5
}
    messages.append({"role": msg.role, "content": msg.content})

    return messages

def check_automation_triggers(business: Business, message_text: str, contact: Contact) -> str | None:
    from .models import AutomationTrigger
    lower_text = message_text.lower()
    triggers = AutomationTrigger.objects.filter(business=business, is_active=True)
    for t in triggers:
        if t.keyword.lower() in lower_text:
            if t.action_type == "reply" and t.response_text:
                return t.response_text
            elif t.action_type == "tag":
                from .models import Tag, ContactTag
                tag, _ = Tag.objects.get_or_create(business=business, name=t.keyword.title())
                ContactTag.objects.get_or_create(contact=contact, tag=tag)
    return None


def get_ai_reply(
    business: Business,
    contact: Contact,
    message_text: str,
    conversation: Conversation = None,
    channel: ChannelConnection = None,
) -> str:
    Message.objects.create(
        business=business,
        contact=contact,
        conversation=conversation,
        channel=channel,
        role="user",
        content=message_text,
    )

    trigger_reply = check_automation_triggers(business, message_text, contact)
    if trigger_reply:
        Message.objects.create(
            business=business,
            contact=contact,
            conversation=conversation,
            channel=channel,
            role="assistant",
            content=trigger_reply,
            status="sent",
        )
        return trigger_reply

    conversation_history = build_conversation_history(business, contact)
    start_time = time.perf_counter()

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=conversation_history,
        )
        reply = response.choices[0].message.content
        status = "sent"
    except Exception as e:
        print(f"Groq Error: {e}")
        reply = "Sorry, I am having trouble thinking right now. Please try again later."
        status = "failed"

    duration = time.perf_counter() - start_time

    Message.objects.create(
        business=business,
        contact=contact,
        conversation=conversation,
        channel=channel,
        role="assistant",
        content=reply,
        status=status,
        response_time=round(duration, 2),
    )

    return reply


def send_whatsapp_message(business: Business, to_number: str, message_text: str):
    from automation.whatsapp.twilio_provider import TwilioWhatsAppProvider
    provider = TwilioWhatsAppProvider()
    return provider.send_text_message(to=to_number, body=message_text)

def send_resend_email(to_email, subject, content):
    resend_key = os.getenv("RESEND_API_KEY")
    url = "https://api.resend.com/emails"

    headers = {
        "Authorization": f"Bearer {resend_key}",
        "Content-Type": "application/json",
    }

    html_content = f"""
    <div style="font-family: sans-serif; color: #333; max-width: 600px; border: 1px solid #eee; padding: 20px;">
        <h2 style="color: #00C853;">Automate NG</h2>
        <p>{content}</p>
        <br />
        <hr />
        <p style="font-size: 12px; color: #888;">This is an automated reply from Zira, your Automate NG Assistant.</p>
    </div>
    """

    payload = {
        "from": "Zira <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    return requests.post(url, json=payload, headers=headers)
