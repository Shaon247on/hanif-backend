"""Contact URL configuration."""

from django.urls import path

from apps.contact import views

urlpatterns = [
    path("terms/", views.TermsAPIView.as_view(), name="terms"),
    path("policy/", views.PolicyAPIView.as_view(), name="policy"),
    path("faqs/", views.FAQListCreateAPIView.as_view(), name="faq-list"),
    path("faqs/<int:pk>/", views.FAQDetailAPIView.as_view(), name="faq-detail"),
    path("contact/", views.ContactCreateAPIView.as_view(), name="contact-create"),
    path("contact/list/", views.ContactListAPIView.as_view(), name="contact-list"),
]
