from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Business, BusinessMember
from .permissions import HasBusinessAccess
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    BusinessSerializer,
    BusinessDetailSerializer,
    BusinessMemberSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "email and password are required"}, status=400)

        from django.contrib.auth import authenticate
        user = authenticate(username=email, password=password)
        if not user:
            return Response({"error": "Invalid credentials"}, status=401)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        })


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass

        return Response({"status": "logged_out"})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class MyBusinessesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = request.user.business_memberships.filter(is_active=True).select_related("business")
        businesses = [m.business for m in memberships]
        return Response(
            {
                "businesses": BusinessSerializer(businesses, many=True).data,
                "memberships": BusinessMemberSerializer(memberships, many=True).data,
            }
        )


class CreateBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        slug = request.data.get("slug")
        whatsapp_phone_number_id = request.data.get("whatsapp_phone_number_id") or None
        whatsapp_access_token = request.data.get("whatsapp_access_token", "")

        if not name or not slug:
            return Response(
                {"error": "name and slug are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if Business.objects.filter(slug=slug).exists():
            return Response(
                {"error": "slug already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        business = Business.objects.create(
            name=name,
            slug=slug,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            whatsapp_access_token=whatsapp_access_token,
            is_active=True,
        )
        BusinessMember.objects.create(
            user=request.user,
            business=business,
            role="owner",
            is_active=True,
        )

        try:
            from billing.models import Subscription
            Subscription.objects.get_or_create(business=business)
        except Exception:
            pass

        return Response(
            BusinessSerializer(business).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request, business_id):
        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response({"error": "Business not found"}, status=404)
        return Response(BusinessDetailSerializer(business).data)

    def patch(self, request, business_id):
        business = Business.objects.filter(id=business_id).first()
        if not business:
            return Response({"error": "Business not found"}, status=404)

        allowed = ["name", "slug", "whatsapp_phone_number_id", "whatsapp_access_token", "system_prompt"]
        for field in allowed:
            if field in request.data:
                setattr(business, field, request.data[field])

        business.save()
        return Response(BusinessDetailSerializer(business).data)


class BusinessMemberListView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def get(self, request, business_id):
        members = BusinessMember.objects.filter(business_id=business_id, is_active=True).select_related("user")
        return Response(BusinessMemberSerializer(members, many=True).data)

    def post(self, request, business_id):
        email = request.data.get("email")
        role = request.data.get("role", "member")

        if not email:
            return Response({"error": "email is required"}, status=400)

        from billing.services import check_member_limit
        from automation.models import Business as BizModel
        business = BizModel.objects.get(id=business_id)
        ok, used, limit = check_member_limit(business)
        if not ok:
            return Response({"error": f"User limit reached ({used}/{limit}). Upgrade your plan to add more users."}, status=400)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found"}, status=404)

        if BusinessMember.objects.filter(business_id=business_id, user=user).exists():
            return Response({"error": "User is already a member"}, status=400)

        member = BusinessMember.objects.create(
            business_id=business_id,
            user=user,
            role=role,
            is_active=True,
        )

        return Response(
            BusinessMemberSerializer(member).data,
            status=201,
        )


class BusinessMemberDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasBusinessAccess]

    def patch(self, request, business_id, member_id):
        member = BusinessMember.objects.filter(id=member_id, business_id=business_id).first()
        if not member:
            return Response({"error": "Member not found"}, status=404)

        role = request.data.get("role")
        if role:
            member.role = role

        is_active = request.data.get("is_active")
        if is_active is not None:
            member.is_active = is_active

        member.save()
        return Response(BusinessMemberSerializer(member).data)

    def delete(self, request, business_id, member_id):
        member = BusinessMember.objects.filter(id=member_id, business_id=business_id).first()
        if not member:
            return Response({"error": "Member not found"}, status=404)

        member.is_active = False
        member.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
