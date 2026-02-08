import base64
import json
import logging
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import InboundEmail


logger = logging.getLogger(__name__)
User = get_user_model()


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


def _resolve_users(payload: dict):
    """Return all ``User``s whose email matches a recipient in the payload.

    Checks *ToFull* entries first (structured), then falls back to the raw
    *To* header.
    """
    to_full = payload.get("ToFull") or []
    candidate_emails = [r["Email"] for r in to_full if r.get("Email")]

    if not candidate_emails:
        raw_to = payload.get("To", "")
        if raw_to:
            candidate_emails = [raw_to]

    return User.objects.filter(email__in=candidate_emails)


def _create_inbound_emails(payload: dict, users) -> list[InboundEmail]:
    """Create one ``InboundEmail`` per user from a Postmark JSON dict."""
    message_id = payload.get("MessageID", "")

    # Filter out users who already have this message
    if message_id:
        existing_user_ids = set(
            InboundEmail.objects.filter(message_id=message_id, user__in=users)
            .values_list("user_id", flat=True)
        )
        users = [user for user in users if user.id not in existing_user_ids]

    from_full = payload.get("FromFull") or {}
    common = dict(
        message_id=message_id,
        from_email=from_full.get("Email") or payload.get("From", ""),
        from_name=from_full.get("Name", ""),
        to=payload.get("To", ""),
        cc=payload.get("Cc", ""),
        bcc=payload.get("Bcc", ""),
        subject=payload.get("Subject", ""),
        text_body=payload.get("TextBody", ""),
        html_body=payload.get("HtmlBody", ""),
        stripped_reply=payload.get("StrippedTextReply", ""),
        tag=payload.get("Tag", ""),
        mailbox_hash=payload.get("MailboxHash", ""),
        headers=payload.get("Headers", []),
        date=payload.get("Date", ""),
        raw_payload=payload,
    )
    return InboundEmail.objects.bulk_create([
        InboundEmail(id=uuid.uuid7(), user=user, **common) for user in users
    ])


@csrf_exempt
@require_POST
def inbound_webhook(request):
    """Receive a Postmark inbound webhook POST.

    Returns 200 on success, 403 on auth failure / no matching user,
    400 on bad payload.
    """
    if not _check_basic_auth(request):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Malformed inbound payload: %s", exc)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    users = _resolve_users(payload)
    if not users.exists():
        logger.warning("No user found for inbound email To=%s – bouncing", payload.get("To", ""))
        return HttpResponse(status=403)

    _create_inbound_emails(payload, users)
    return HttpResponse(status=200)
