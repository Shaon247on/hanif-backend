"""URL configuration for the project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from config import env as env_module

# ---------------------------------------------------------------------------
# Swagger / OpenAPI schema
# ---------------------------------------------------------------------------
swagger_info = openapi.Info(
    title=env_module.PROJECT_NAME,
    default_version=env_module.PROJECT_VERSION,
    description=env_module.PROJECT_DESCRIPTION,
    terms_of_service="https://www.google.com/policies/terms/",
    license=openapi.License(name="BSD License"),
)

schema_view = get_schema_view(
    swagger_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
def health_check(request):
    """Simple health check endpoint for load balancers and monitoring."""
    return JsonResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("api/v1/", include("apps.user.urls")),
    path("api/v1/", include("apps.contact.urls")),
    path("api/v1/", include("apps.booking.urls")),
    path("api/v1/", include("apps.shop.urls")),
    path("api/v1/", include("apps.barber.urls")),
    path("api/v1/", include("apps.service.urls")),
    path("api/v1/", include("apps.notification.urls")),
    path("api/v1/", include("apps.payment.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/schedule/", include("apps.schedule.urls")),
]


# Serve media files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Django Debug Toolbar URLs
if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]


# Swagger — conditional
if not env_module.DISABLE_SWAGGER:
    urlpatterns += [
        path(
            "swagger/",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
        path(
            "redoc/",
            schema_view.with_ui("redoc", cache_timeout=0),
            name="schema-redoc",
        ),
    ]

# Admin — conditional
if not env_module.DISABLE_ADMIN:
    urlpatterns += [
        path("admin/", admin.site.urls),
    ]
