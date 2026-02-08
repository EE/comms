from .models import InboundEmail


def create_inbound_email(payload: dict) -> InboundEmail:
    """Create and save an ``InboundEmail`` from a Postmark JSON dict."""
    from_full = payload.get("FromFull") or {}
    return InboundEmail.objects.create(
        message_id=payload.get("MessageID", ""),
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
