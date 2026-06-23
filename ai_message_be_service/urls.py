from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path("", include("automation.urls")),
    path('billing/', include('billing.urls')),
    path("", include("billing.urls")),
]
