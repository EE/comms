import base64
import json

import pytest
from django.urls import reverse

from postmark.models import InboundEmail


def _basic_auth_header(username, password):
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


INBOUND_PAYLOAD = {
    "FromName": "Postmarkapp Support",
    "MessageStream": "inbound",
    "From": "support@postmarkapp.com",
    "FromFull": {
        "Email": "support@postmarkapp.com",
        "Name": "Postmarkapp Support",
        "MailboxHash": "",
    },
    "To": '"Firstname Lastname" <yourhash+SampleHash@inbound.postmarkapp.com>',
    "ToFull": [
        {
            "Email": "yourhash+SampleHash@inbound.postmarkapp.com",
            "Name": "Firstname Lastname",
            "MailboxHash": "SampleHash",
        }
    ],
    "Cc": "cc@example.com",
    "CcFull": [{"Email": "cc@example.com", "Name": "", "MailboxHash": ""}],
    "Bcc": "",
    "BccFull": [],
    "OriginalRecipient": "yourhash+SampleHash@inbound.postmarkapp.com",
    "Subject": "Test subject",
    "MessageID": "73e6d360-66eb-11e1-8e72-a8904824019b",
    "ReplyTo": "replyto@postmarkapp.com",
    "MailboxHash": "SampleHash",
    "Date": "Fri, 1 Aug 2014 16:45:32 -04:00",
    "TextBody": "This is a test text body.",
    "HtmlBody": "<html><body><p>This is a test html body.</p></body></html>",
    "StrippedTextReply": "This is the reply text",
    "Tag": "TestTag",
    "Headers": [
        {"Name": "X-Header-Test", "Value": ""},
        {"Name": "X-Spam-Status", "Value": "No"},
        {"Name": "X-Spam-Score", "Value": "-0.1"},
        {"Name": "X-Spam-Tests", "Value": "DKIM_SIGNED,DKIM_VALID,DKIM_VALID_AU,SPF_PASS"},
    ],
    "Attachments": [],
}

WEBHOOK_URL = "/postmark/inbound/"


def test_url_name():
    url = reverse("postmark:inbound-webhook")
    assert url == WEBHOOK_URL


@pytest.mark.parametrize(
    "auth_header, expected_status, expected_count",
    [
        (_basic_auth_header("user", "pass"), 200, 1),
        (_basic_auth_header("user", "wrong"), 403, 0),
        (None, 403, 0),
    ],
    ids=["valid-creds", "wrong-password", "no-auth"],
)
@pytest.mark.django_db
def test_webhook_auth(client, settings, auth_header, expected_status, expected_count):
    settings.POSTMARK_WEBHOOK_USERNAME = 'user'
    settings.POSTMARK_WEBHOOK_PASSWORD = 'pass'
    kwargs = {}
    if auth_header is not None:
        kwargs["HTTP_AUTHORIZATION"] = auth_header
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        **kwargs,
    )
    assert resp.status_code == expected_status
    assert InboundEmail.objects.count() == expected_count


def test_empty_configured_password_rejects(settings, client):
    settings.POSTMARK_WEBHOOK_USERNAME = "user"
    settings.POSTMARK_WEBHOOK_PASSWORD = ""
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        HTTP_AUTHORIZATION=_basic_auth_header("user", ""),
    )
    assert resp.status_code == 403


def test_get_not_allowed(client):
    resp = client.get(WEBHOOK_URL)
    assert resp.status_code == 405


def test_invalid_json_returns_400(client, auth_header):
    resp = client.post(
        WEBHOOK_URL,
        data="not json",
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 400


@pytest.fixture(name="auth_header")
def auth_header_fixture(settings):
    settings.POSTMARK_WEBHOOK_USERNAME = "user"
    settings.POSTMARK_WEBHOOK_PASSWORD = "pass"
    return _basic_auth_header("user", "pass")


@pytest.mark.django_db
def test_creates_inbound_email(client, auth_header):
    assert InboundEmail.objects.count() == 0
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    assert InboundEmail.objects.count() == 1

    email = InboundEmail.objects.get()
    assert email.message_id == "73e6d360-66eb-11e1-8e72-a8904824019b"
    assert email.from_email == "support@postmarkapp.com"
    assert email.from_name == "Postmarkapp Support"
    assert email.subject == "Test subject"
    assert email.text_body == "This is a test text body."
    assert email.html_body == "<html><body><p>This is a test html body.</p></body></html>"
    assert email.stripped_reply == "This is the reply text"
    assert email.tag == "TestTag"
    assert email.mailbox_hash == "SampleHash"
    assert email.cc == "cc@example.com"
    assert email.date == "Fri, 1 Aug 2014 16:45:32 -04:00"
    assert len(email.headers) == 4
    assert email.raw_payload["MessageID"] == email.message_id


@pytest.mark.django_db
def test_duplicate_message_id_returns_200_no_duplicate(client, auth_header):
    """Second POST with the same MessageID should not create a duplicate."""
    client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    assert InboundEmail.objects.count() == 1


@pytest.mark.django_db
def test_minimal_payload(client, auth_header):
    """A very sparse payload should still succeed."""
    payload = {"MessageID": "minimal-1", "From": "a@b.com"}
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    email = InboundEmail.objects.get()
    assert email.message_id == "minimal-1"
    assert email.from_email == "a@b.com"
    assert email.subject == ""
