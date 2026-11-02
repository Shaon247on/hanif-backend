from django.urls import path

from .client_views import (
    ClientDetailAPIView,
    ClientImportAPIView,
    ClientListCreateAPIView,
    ClientMessageAPIView,
)
from .message_views import (
    ClientDirectMessagesAPIView,
    ClientGroupDetailAPIView,
    ClientGroupListCreateAPIView,
    ClientGroupMessagesAPIView,
    MyDirectMessagesAPIView,
    MyGroupMessagesAPIView,
    MyMessagesAPIView,
)
from .review_views import AdminReviewListAPIView
from .staff_views import AdminStaffDetailAPIView, AdminStaffListCreateAPIView
from .views import AdminDashboardAPIView
from .report_views import AdminReportAPIView

urlpatterns = [
    # Dashboard stats
    path("", AdminDashboardAPIView.as_view(), name="admin-dashboard"),
    path("reports/", AdminReportAPIView.as_view(), name="admin-reports"),
    # Staff / Barbers
    path("shops/<int:shop_id>/staff/", AdminStaffListCreateAPIView.as_view(), name="dashboard-staff-list-create"),
    path("shops/<int:shop_id>/staff/<int:pk>/", AdminStaffDetailAPIView.as_view(), name="dashboard-staff-detail"),
    # Reviews
    path("shops/<int:shop_id>/reviews/", AdminReviewListAPIView.as_view(), name="dashboard-reviews"),
    # Client Management
    path("clients/", ClientListCreateAPIView.as_view(), name="dashboard-clients-list-create-base"),
    path("shops/<int:shop_id>/clients/import/", ClientImportAPIView.as_view(), name="dashboard-clients-import"),
    path("shops/<int:shop_id>/clients/", ClientListCreateAPIView.as_view(), name="dashboard-clients-list-create"),
    path("shops/<int:shop_id>/clients/<uuid:pk>/", ClientDetailAPIView.as_view(), name="dashboard-client-detail"),
    path("shops/<int:shop_id>/client-groups/", ClientGroupListCreateAPIView.as_view(), name="dashboard-client-groups"),
    path(
        "shops/<int:shop_id>/client-groups/<int:pk>/",
        ClientGroupDetailAPIView.as_view(),
        name="dashboard-client-group-detail",
    ),
    path(
        "shops/<int:shop_id>/client-groups/<int:pk>/messages/",
        ClientGroupMessagesAPIView.as_view(),
        name="dashboard-client-group-messages",
    ),
    path(
        "shops/<int:shop_id>/clients/<uuid:client_id>/messages/",
        ClientDirectMessagesAPIView.as_view(),
        name="dashboard-client-direct-messages",
    ),
    path("shops/<int:shop_id>/send-messages/", ClientMessageAPIView.as_view(), name="dashboard-client-messages"),
    # Customer inbox
    path("my-messages/", MyMessagesAPIView.as_view(), name="my-messages"),
    path("my-messages/groups/<int:pk>/", MyGroupMessagesAPIView.as_view(), name="my-group-messages"),
    path("my-messages/shops/<int:shop_id>/", MyDirectMessagesAPIView.as_view(), name="my-direct-messages"),
]
