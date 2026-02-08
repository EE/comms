import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class InboundEmail(models.Model):
    """An email received via the Postmark inbound webhook."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    # The user whose inbox this email belongs to.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbound_emails",
    )

    # Postmark's unique identifier for this message.
    message_id = models.CharField(max_length=255)

    # Sender
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)

    # Recipients (stored as the raw header strings – can contain multiple)
    to = models.TextField()
    cc = models.TextField(blank=True)
    bcc = models.TextField(blank=True)

    subject = models.CharField(max_length=1000, blank=True)
    text_body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)
    stripped_reply = models.TextField(
        blank=True,
        help_text="Parsed reply text (StrippedTextReply).",
    )

    tag = models.CharField(max_length=255, blank=True)
    mailbox_hash = models.CharField(
        max_length=255, blank=True,
        help_text="The +hash portion of the inbound address.",
    )

    # Keep the full headers and raw payload for debugging / re-processing.
    headers = models.JSONField(default=list, blank=True)
    raw_payload = models.JSONField(
        default=dict, blank=True,
        help_text="Complete JSON payload as received from Postmark.",
    )

    # When *Postmark* says the email was sent (parsed from the Date header).
    date = models.CharField(
        max_length=255, blank=True,
        help_text="Original Date header value from the email.",
    )

    class Meta:
        ordering = ["user", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "message_id"],
                name="unique_user_message",
            ),
        ]
