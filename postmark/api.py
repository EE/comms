import email.utils as _email_utils

import httpx
from django.conf import settings
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .models import InboundEmail


POSTMARK_BASE_URL = "https://api.postmarkapp.com"


def _postmark_headers():
    return {
        "Accept": "application/json",
        "X-Postmark-Server-Token": settings.POSTMARK_SERVER_TOKEN,
    }


# ── Inbox (inbound) ────────────────────────────────────────────────


class InboundEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboundEmail
        fields = [
            "id",
            "message_id",
            "from_email",
            "from_name",
            "to",
            "cc",
            "bcc",
            "subject",
            "text_body",
            "html_body",
            "stripped_reply",
            "tag",
            "mailbox_hash",
            "date",
            "created_at",
        ]
        read_only_fields = fields


class InboxViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Authenticated user's inbox.

    list   – GET    /api/inbox/       → emails routed to the current user
    detail – GET    /api/inbox/{id}/  → single email (must belong to user)
    delete – DELETE /api/inbox/{id}/  → delete an email from user's inbox
    """

    serializer_class = InboundEmailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return InboundEmail.objects.filter(user=self.request.user)


# ── Send email (outbound) ──────────────────────────────────────────


class SendEmailSerializer(serializers.Serializer):
    from_email = serializers.CharField(max_length=255)
    to = serializers.CharField()
    cc = serializers.CharField(required=False, allow_blank=True, default="")
    bcc = serializers.CharField(required=False, allow_blank=True, default="")
    subject = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default="",
    )
    html_body = serializers.CharField(required=False, allow_blank=True, default="")
    text_body = serializers.CharField(required=False, allow_blank=True, default="")
    reply_to = serializers.CharField(required=False, allow_blank=True, default="")
    tag = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=1000,
    )
    track_opens = serializers.BooleanField(required=False, default=False)
    track_links = serializers.ChoiceField(
        choices=["None", "HtmlAndText", "HtmlOnly", "TextOnly"],
        required=False,
        default="None",
    )
    message_stream = serializers.CharField(required=False, default="outbound")
    metadata = serializers.DictField(
        child=serializers.CharField(), required=False, default=dict,
    )

    def validate_from_email(self, value):
        _, addr = _email_utils.parseaddr(value)
        if not addr:
            raise serializers.ValidationError("Invalid email address.")
        user = self.context["request"].user
        if not user.email:
            raise serializers.ValidationError(
                "Your account has no email address configured."
            )
        if addr.lower() != user.email.lower():
            raise serializers.ValidationError(
                f"Sender address must be {user.email}."
            )
        return value

    def validate(self, data):
        if not data.get("html_body") and not data.get("text_body"):
            raise serializers.ValidationError(
                "At least one of html_body or text_body is required."
            )
        return data


def _build_postmark_payload(data):
    """Turn validated serializer data into a Postmark API payload."""
    payload = {
        "From": data["from_email"],
        "To": data["to"],
        "Subject": data.get("subject", ""),
        "MessageStream": data.get("message_stream", "outbound"),
    }
    _optional = [
        ("cc", "Cc"),
        ("bcc", "Bcc"),
        ("html_body", "HtmlBody"),
        ("text_body", "TextBody"),
        ("reply_to", "ReplyTo"),
        ("tag", "Tag"),
    ]
    for src, dst in _optional:
        if data.get(src):
            payload[dst] = data[src]
    if data.get("track_opens"):
        payload["TrackOpens"] = True
    if data.get("track_links", "None") != "None":
        payload["TrackLinks"] = data["track_links"]
    if data.get("metadata"):
        payload["Metadata"] = data["metadata"]
    return payload


# ── Outbound messages (list / detail / send) ────────────────────────


class OutboundMessageViewSet(viewsets.GenericViewSet):
    """
    Outbound messages via Postmark.

    create   – POST   /api/outbound-messages/       → send an email
    list     – GET    /api/outbound-messages/        → search sent messages
    retrieve – GET    /api/outbound-messages/{id}/   → message details
    """

    serializer_class = SendEmailSerializer

    # -- create (send) ------------------------------------------------

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = _build_postmark_payload(serializer.validated_data)
        resp = httpx.post(
            f"{POSTMARK_BASE_URL}/email",
            json=payload,
            headers=_postmark_headers(),
        )
        return Response(resp.json(), status=resp.status_code)

    # -- list (search) -------------------------------------------------

    _LIST_PARAMS = [
        "count", "offset", "recipient", "tag", "status",
        "todate", "fromdate", "subject", "messagestream",
    ]

    def list(self, request, *args, **kwargs):
        params = {
            k: request.query_params[k]
            for k in self._LIST_PARAMS
            if k in request.query_params
        }
        params.setdefault("count", "20")
        params.setdefault("offset", "0")
        # Always scope to the caller's own email.
        params["fromemail"] = request.user.email

        resp = httpx.get(
            f"{POSTMARK_BASE_URL}/messages/outbound",
            params=params,
            headers=_postmark_headers(),
        )
        return Response(resp.json(), status=resp.status_code)

    # -- retrieve (details) --------------------------------------------

    def retrieve(self, request, *args, **kwargs):
        message_id = self.kwargs[self.lookup_field]
        resp = httpx.get(
            f"{POSTMARK_BASE_URL}/messages/outbound/{message_id}/details",
            headers=_postmark_headers(),
        )
        if resp.status_code != 200:
            return Response(resp.json(), status=resp.status_code)

        data = resp.json()
        _, from_addr = _email_utils.parseaddr(data.get("From", ""))
        if from_addr.lower() != request.user.email.lower():
            raise NotFound

        return Response(data)
