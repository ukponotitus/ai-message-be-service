import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework import status as drf_status

from .models import Transaction, Subscription
from .services import get_plan_limits, check_contact_limit, check_channel_limit, check_member_limit, check_automation_limit, PLANS
from automation.models import Contact, ChannelConnection, AutomationFlow


class PaystackVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reference = request.data.get("reference")
        business_id = request.data.get("business_id")
        plan_selected = request.data.get("plan")
        billing_cycle = request.data.get("billing_cycle", "monthly")

        if not all([reference, business_id, plan_selected]):
            return Response({"error": "reference, business_id, and plan are required"}, status=400)

        if plan_selected not in PLANS or plan_selected == 'free':
            return Response({"error": "Invalid plan"}, status=400)

        if billing_cycle not in ('monthly', 'annual'):
            return Response({"error": "billing_cycle must be monthly or annual"}, status=400)

        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        url = f"https://api.paystack.co/transaction/verify/{reference}"

        try:
            res = requests.get(url, headers=headers, timeout=15).json()
        except requests.RequestException as e:
            return Response({"error": f"Paystack verification request failed: {str(e)}"}, status=502)
        except ValueError as e:
            return Response({"error": f"Invalid response from Paystack: {str(e)}"}, status=502)

        if not res.get('status'):
            msg = res.get('message', 'Paystack verification returned false')
            return Response({"error": msg}, status=400)

        data = res.get('data', {})
        if data.get('status') != 'success':
            return Response({"error": f"Payment not successful (status: {data.get('status')})"}, status=400)

        try:
            Transaction.objects.create(
                business_id=business_id,
                reference=reference,
                amount=data['amount'] / 100,
                plan_type=plan_selected,
                billing_cycle=billing_cycle,
                status='success'
            )

            sub, _ = Subscription.objects.get_or_create(business_id=business_id)
            sub.plan = plan_selected
            sub.billing_cycle = billing_cycle
            days = 365 if billing_cycle == 'annual' else 30
            sub.expires_at = timezone.now() + timedelta(days=days)
            sub.is_active = True
            sub.save()

            return Response({
                "status": "Subscription updated successfully!",
                "plan": plan_selected,
                "billing_cycle": billing_cycle,
                "expires_at": sub.expires_at.isoformat(),
            })
        except Exception as e:
            return Response({"error": f"Failed to save subscription: {str(e)}"}, status=500)


class SubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        business_id = request.query_params.get("business_id")
        if not business_id:
            membership = request.user.business_memberships.filter(is_active=True).first()
            if not membership:
                return Response({"error": "No business found"}, status=404)
            business_id = membership.business_id

        sub = Subscription.objects.filter(business_id=business_id).first()
        if not sub:
            return Response({
                "plan": "free",
                "billing_cycle": "monthly",
                "expires_at": None,
                "is_active": True,
                "complimentary": False,
            })

        limits = get_plan_limits(sub.plan)
        contact_ok, contact_count, contact_limit = check_contact_limit(sub.business)
        channel_ok, channel_count, channel_limit = check_channel_limit(sub.business)
        member_ok, member_count, member_limit = check_member_limit(sub.business)
        automation_ok, automation_count, automation_limit = check_automation_limit(sub.business)

        return Response({
            "plan": sub.plan,
            "billing_cycle": sub.billing_cycle,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "is_active": sub.is_active,
            "complimentary": sub.complimentary,
            "limits": limits,
            "usage": {
                "contacts": {"used": contact_count, "limit": contact_limit, "ok": contact_ok},
                "channels": {"used": channel_count, "limit": channel_limit, "ok": channel_ok},
                "users": {"used": member_count, "limit": member_limit, "ok": member_ok},
                "automations": {"used": automation_count, "limit": automation_limit, "ok": automation_ok},
            },
        })


class InitializePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        business_id = request.data.get("business_id")
        plan = request.data.get("plan")
        billing_cycle = request.data.get("billing_cycle", "monthly")

        if not all([business_id, plan]):
            return Response({"error": "business_id and plan are required"}, status=400)

        if plan not in PLANS or plan == 'free':
            return Response({"error": "Invalid plan"}, status=400)

        if billing_cycle not in ('monthly', 'annual'):
            return Response({"error": "billing_cycle must be monthly or annual"}, status=400)

        from .services import PLAN_PRICES
        amount = PLAN_PRICES.get(plan, {}).get(billing_cycle)
        if not amount:
            return Response({"error": "Price not found for this plan/billing_cycle"}, status=400)

        import uuid
        reference = f"auto-{uuid.uuid4().hex[:12]}"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "email": request.user.email,
            "amount": str(amount),
            "reference": reference,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback?reference={reference}&business_id={business_id}&plan={plan}&billing_cycle={billing_cycle}",
            "metadata": {
                "business_id": business_id,
                "plan": plan,
                "billing_cycle": billing_cycle,
            },
        }

        try:
            res = requests.post(
                "https://api.paystack.co/transaction/initialize",
                headers=headers,
                json=payload,
                timeout=15,
            ).json()
        except requests.RequestException as e:
            return Response({"error": f"Paystack initialization request failed: {str(e)}"}, status=502)
        except ValueError as e:
            return Response({"error": f"Invalid response from Paystack: {str(e)}"}, status=502)

        if res.get('status'):
            try:
                Transaction.objects.create(
                    business_id=business_id,
                    reference=reference,
                    amount=amount / 100,
                    plan_type=plan,
                    billing_cycle=billing_cycle,
                    status='pending',
                )
            except Exception as e:
                return Response({"error": f"Failed to save transaction: {str(e)}"}, status=500)

            data = res.get('data', {})
            return Response({
                "authorization_url": data.get('authorization_url'),
                "reference": reference,
                "access_code": data.get('access_code'),
            })

        msg = res.get('message', 'Payment initialization failed')
        return Response({"error": msg}, status=400)


class SuperAdminSubscriptionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, business_id):
        complimentary = request.data.get("complimentary")
        if complimentary is None:
            return Response({"error": "complimentary field is required"}, status=400)

        sub, _ = Subscription.objects.get_or_create(business_id=business_id)
        sub.complimentary = bool(complimentary)
        if sub.complimentary:
            sub.is_active = True
        sub.save()

        return Response({
            "status": "Subscription updated",
            "business_id": business_id,
            "complimentary": sub.complimentary,
            "plan": sub.plan,
            "is_active": sub.is_active,
        })
