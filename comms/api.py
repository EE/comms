from rest_framework.routers import DefaultRouter

from postmark.api import InboxViewSet


router = DefaultRouter()
router.register("inbound-emails", InboxViewSet, basename="inbound-email")
extra_urls = []
