import uuid

from django.db import models


class InboundEmail(models.Model):
    """An email received via the Postmark inbound webhook."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)

    # Postmark's unique identifier for this message.
    message_id = models.CharField(max_length=255, unique=True)

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

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_email}: {self.subject}" if self.subject else self.from_email
