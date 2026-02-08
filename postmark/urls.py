from django.urls import path

from .inbound_webhook import inbound_webhook


app_name = "postmark"

urlpatterns = [
    path("inbound/", inbound_webhook, name="inbound-webhook"),
]
