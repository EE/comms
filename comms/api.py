from pathlib import Path

from django.views.static import serve
from rest_framework.routers import DefaultRouter

from postmark.api import InboxViewSet, OutboundMessageViewSet


_SKILL_PATH = Path(__file__).resolve().parent


def skill_md(request):
    return serve(request, "skill.md", document_root=str(_SKILL_PATH))


router = DefaultRouter()
router.register("inbound-emails", InboxViewSet, basename="inbound-email")
router.register(
    "outbound-messages", OutboundMessageViewSet, basename="outbound-message",
)
extra_urls = []
