from django.urls import path

from .views import inbound_webhook

app_name = "postmark"

urlpatterns = [
    path("inbound/", inbound_webhook, name="inbound-webhook"),
]
