import base64
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import InboundEmail
from .services import create_inbound_email

logger = logging.getLogger(__name__)


def _check_basic_auth(request):
    """Verify HTTP Basic Auth credentials against settings."""
    expected_user = settings.POSTMARK_WEBHOOK_USERNAME
    expected_pass = settings.POSTMARK_WEBHOOK_PASSWORD
    if not expected_user or not expected_pass:
        logger.warning("POSTMARK_WEBHOOK_USERNAME or POSTMARK_WEBHOOK_PASSWORD not set; rejecting all webhook requests")
        return False
    expected_auth = "Basic " + base64.b64encode(f"{expected_user}:{expected_pass}".encode()).decode()
    actual_auth = request.headers.get("Authorization", "")
    return actual_auth == expected_auth


@csrf_exempt
@require_POST
def inbound_webhook(request):
    """Receive a Postmark inbound webhook POST.

    Returns 200 on success, 403 on auth failure, 400 on bad payload.
    """
    if not _check_basic_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Malformed inbound payload: %s", exc)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    message_id = payload.get("MessageID", "")
    if not message_id or not InboundEmail.objects.filter(message_id=message_id).exists():
        create_inbound_email(payload)

    return HttpResponse(status=200)
