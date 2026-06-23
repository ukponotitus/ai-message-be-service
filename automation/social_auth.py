from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework import serializers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SocialAccount
from .serializers import UserSerializer
import requests as http_requests

User = get_user_model()



User = get_user_model()

class SocialLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(required=False, allow_null=True)
    id_token = serializers.CharField(required=False, allow_null=True)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

def create_or_update_user(email, first_name, last_name, picture, provider, provider_id):
    social_account = SocialAccount.objects.filter(
        provider=provider, provider_id=provider_id
    ).select_related("user").first()

    if social_account:
        return social_account.user, False

    existing_user = User.objects.filter(email=email).first()

    if existing_user:
        user = existing_user
        if not user.first_name and first_name:
            user.first_name = first_name
        if not user.last_name and last_name:
            user.last_name = last_name
        user.save()
    else:
        username = email or f"{provider}_{provider_id}"
        user = User.objects.create_user(
            username=username,
            email=email or "",
            first_name=first_name or "",
            last_name=last_name or "",
        )

    SocialAccount.objects.create(
        user=user,
        provider=provider,
        provider_id=provider_id,
    )
    return user, True

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = serializer.validated_data.get("access_token")
        
        if not access_token:
            return Response({"error": "access_token is required"}, status=400)

        # 1. Use the access_token to get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        response = http_requests.get(user_info_url, params={'access_token': access_token})
        
        if response.status_code != 200:
            return Response({"error": "Invalid Google Token"}, status=status.HTTP_401_UNAUTHORIZED)

        user_data = response.json()

        # 2. Create or Login the user
        user, created = create_or_update_user(
            email=user_data.get("email"),
            first_name=user_data.get("given_name", ""),
            last_name=user_data.get("family_name", ""),
            picture=user_data.get("picture", ""),
            provider="google",
            provider_id=user_data.get("sub"), # 'sub' is the unique Google ID
        )

        tokens = get_tokens_for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            **tokens,
        })

class FacebookLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = serializer.validated_data.get("access_token")
        if not access_token:
            return Response(
                {"error": "access_token is required for Facebook"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import requests as http_requests

        app_id = settings.FACEBOOK_APP_ID
        app_secret = settings.FACEBOOK_APP_SECRET

        app_token = f"{app_id}|{app_secret}"

        debug_url = "https://graph.facebook.com/debug_token"
        debug_params = {
            "input_token": access_token,
            "access_token": app_token,
        }

        debug_resp = http_requests.get(debug_url, params=debug_params)
        if debug_resp.status_code != 200:
            return Response(
                {"error": "Failed to verify Facebook token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        debug_data = debug_resp.json().get("data", {})

        if not debug_data.get("is_valid"):
            return Response(
                {"error": "Facebook token is invalid or expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if debug_data.get("app_id") != app_id:
            return Response(
                {"error": "Token app ID mismatch"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        fb_user_id = debug_data.get("user_id")
        if not fb_user_id:
            return Response(
                {"error": "Could not extract user ID from Facebook token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile_url = "https://graph.facebook.com/me"
        profile_params = {
            "fields": "id,name,email,picture",
            "access_token": access_token,
        }

        profile_resp = http_requests.get(profile_url, params=profile_params)
        if profile_resp.status_code != 200:
            return Response(
                {"error": "Failed to fetch Facebook profile"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = profile_resp.json()

        full_name = profile.get("name", "").strip()
        name_parts = full_name.split(" ", 1) if full_name else ["", ""]
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        picture_data = profile.get("picture", {})
        picture_url = picture_data.get("data", {}).get("url", "") if picture_data else ""

        if not profile.get("email"):
            return Response(
                {"error": "Email not provided by Facebook. Ensure email permission is granted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = create_or_update_user(
            email=profile.get("email"),
            first_name=first_name,
            last_name=last_name,
            picture=picture_url,
            provider="facebook",
            provider_id=fb_user_id,
        )

        tokens = get_tokens_for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            **tokens,
        })
