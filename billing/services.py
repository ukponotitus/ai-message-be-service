from django.utils import timezone
from .models import Subscription

PLANS = {
    'free': {
        'contacts': 20,
        'channels': 1,
        'users': 1,
        'automations': 2,
        'ai_assistant': False,
        'branding': True,
    },
    'essential': {
        'contacts': 250,
        'channels': 2,
        'users': 2,
        'automations': 999,
        'ai_assistant': False,
        'branding': False,
    },
    'pro': {
        'contacts': 2500,
        'channels': 3,
        'users': 3,
        'automations': 999,
        'ai_assistant': True,
        'branding': False,
    },
    'business': {
        'contacts': 7500,
        'channels': 999,
        'users': 5,
        'automations': 999,
        'ai_assistant': True,
        'branding': False,
    },
    'advanced': {
        'contacts': 25000,
        'channels': 999,
        'users': 10,
        'automations': 999,
        'ai_assistant': True,
        'branding': False,
    },
}

PLAN_PRICES = {
    'essential': {'monthly': 2500000, 'annual': 25000000},
    'pro': {'monthly': 5500000, 'annual': 55000000},
    'business': {'monthly': 14000000, 'annual': 140000000},
    'advanced': {'monthly': 28000000, 'annual': 280000000},
}

def get_plan_limits(plan_name):
    return PLANS.get(plan_name, PLANS['free'])

def is_complimentary(business):
    try:
        return business.subscription.complimentary
    except (Subscription.DoesNotExist, AttributeError):
        return False

def check_contact_limit(business):
    if is_complimentary(business):
        from automation.models import Contact
        return True, Contact.objects.filter(business=business).count(), 999999
    limits = get_plan_limits(business.subscription.plan)
    from automation.models import Contact
    count = Contact.objects.filter(business=business).count()
    return count < limits['contacts'], count, limits['contacts']

def check_channel_limit(business):
    if is_complimentary(business):
        from automation.models import ChannelConnection
        return True, ChannelConnection.objects.filter(business=business, is_active=True).count(), 999999
    limits = get_plan_limits(business.subscription.plan)
    from automation.models import ChannelConnection
    count = ChannelConnection.objects.filter(business=business, is_active=True).count()
    return count < limits['channels'], count, limits['channels']

def check_member_limit(business):
    if is_complimentary(business):
        return True, business.members.filter(is_active=True).count(), 999999
    limits = get_plan_limits(business.subscription.plan)
    count = business.members.filter(is_active=True).count()
    return count < limits['users'], count, limits['users']

def check_automation_limit(business):
    if is_complimentary(business):
        from automation.models import AutomationFlow
        return True, AutomationFlow.objects.filter(business=business, is_active=True).count(), 999999
    limits = get_plan_limits(business.subscription.plan)
    from automation.models import AutomationFlow
    count = AutomationFlow.objects.filter(business=business, is_active=True).count()
    return count < limits['automations'], count, limits['automations']

def can_business_send_message(business):
    try:
        sub = business.subscription
        if sub.complimentary:
            return True
        if sub.plan == 'free':
            ok, used, limit = check_contact_limit(business)
            if not ok:
                return False
            return True
        if sub.expires_at and sub.expires_at < timezone.now():
            return False
        return sub.is_active
    except Subscription.DoesNotExist:
        return True
