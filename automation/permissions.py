from rest_framework.permissions import BasePermission


def resolve_business_id(request):
    query = getattr(request, "query_params", request.GET)
    data = getattr(request, "data", request.POST)
    business_id = query.get("business_id") or data.get("business_id")

    if not business_id and request.user.is_authenticated:
        membership = request.user.business_memberships.filter(is_active=True).first()
        if membership:
            business_id = membership.business_id

    return business_id


class HasBusinessAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        query = getattr(request, "query_params", request.GET)
        data = getattr(request, "data", request.POST)
        business_id = query.get("business_id") or data.get("business_id")

        if not business_id:
            membership = user.business_memberships.filter(is_active=True).first()
            return membership is not None

        return user.business_memberships.filter(
            business_id=business_id, is_active=True
        ).exists()
