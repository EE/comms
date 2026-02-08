import base64
import json

import pytest
from django.urls import reverse

from postmark.models import InboundEmail
from users.models import User


def _basic_auth_header(username, password):
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


RECIPIENT_EMAIL = "yourhash+SampleHash@inbound.postmarkapp.com"

INBOUND_PAYLOAD = {
    "FromName": "Postmarkapp Support",
    "MessageStream": "inbound",
    "From": "support@postmarkapp.com",
    "FromFull": {
        "Email": "support@postmarkapp.com",
        "Name": "Postmarkapp Support",
        "MailboxHash": "",
    },
    "To": f'"Firstname Lastname" <{RECIPIENT_EMAIL}>',
    "ToFull": [
        {
            "Email": RECIPIENT_EMAIL,
            "Name": "Firstname Lastname",
            "MailboxHash": "SampleHash",
        }
    ],
    "Cc": "cc@example.com",
    "CcFull": [{"Email": "cc@example.com", "Name": "", "MailboxHash": ""}],
    "Bcc": "",
    "BccFull": [],
    "OriginalRecipient": RECIPIENT_EMAIL,
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


@pytest.fixture(name="auth_header")
def auth_header_fixture(settings):
    settings.POSTMARK_WEBHOOK_USERNAME = "user"
    settings.POSTMARK_WEBHOOK_PASSWORD = "pass"
    return _basic_auth_header("user", "pass")


@pytest.fixture(name="recipient_user")
def recipient_user_fixture(db):
    """A user whose email matches the To address in the payload."""
    return User.objects.create_user(
        username="recipient",
        email=RECIPIENT_EMAIL,
        password="testpass",
    )


def test_url_name():
    url = reverse("postmark:inbound-webhook")
    assert url == WEBHOOK_URL


# ── Auth ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "auth_header, expected_status",
    [
        (_basic_auth_header("user", "pass"), 200),
        (_basic_auth_header("user", "wrong"), 403),
        (None, 403),
    ],
    ids=["valid-creds", "wrong-password", "no-auth"],
)
@pytest.mark.django_db
def test_webhook_auth(client, settings, recipient_user, auth_header, expected_status):
    settings.POSTMARK_WEBHOOK_USERNAME = "user"
    settings.POSTMARK_WEBHOOK_PASSWORD = "pass"
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


# ── Email creation & routing ────────────────────────────────────────


@pytest.mark.django_db
def test_creates_inbound_email_routed_to_user(client, auth_header, recipient_user):
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
    assert email.user == recipient_user
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
def test_multiple_matching_users_creates_one_email_each(client, auth_header):
    """When two users match recipients, both get a copy."""
    user_a = User.objects.create_user(username="a", email="a@test.com", password="p")
    user_b = User.objects.create_user(username="b", email="b@test.com", password="p")
    payload = {
        **INBOUND_PAYLOAD,
        "MessageID": "multi-1",
        "ToFull": [
            {"Email": "a@test.com", "Name": "A", "MailboxHash": ""},
            {"Email": "b@test.com", "Name": "B", "MailboxHash": ""},
        ],
    }
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    assert InboundEmail.objects.count() == 2
    assert set(InboundEmail.objects.values_list("user_id", flat=True)) == {user_a.pk, user_b.pk}


@pytest.mark.django_db
def test_no_matching_user_returns_403(client, auth_header):
    """Webhook returns 403 when no user matches, stopping Postmark retries."""
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(INBOUND_PAYLOAD),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 403
    assert InboundEmail.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_message_id_returns_200_no_duplicate(client, auth_header, recipient_user):
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
def test_minimal_payload_routes_by_raw_to(client, auth_header):
    """A sparse payload without ToFull falls back to raw To for routing."""
    user = User.objects.create_user(
        username="minuser", email="a@b.com", password="p",
    )
    payload = {"MessageID": "minimal-1", "From": "sender@x.com", "To": "a@b.com"}
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    email = InboundEmail.objects.get()
    assert email.user == user
    assert email.message_id == "minimal-1"
    assert email.from_email == "sender@x.com"
    assert email.subject == ""


@pytest.mark.django_db
def test_redelivery_with_changed_users_creates_only_for_new_users(client, auth_header):
    """When a message is redelivered with a different user set, only create for new users."""
    user_a = User.objects.create_user(username="a", email="a@test.com", password="p")
    user_b = User.objects.create_user(username="b", email="b@test.com", password="p")

    payload = {
        **INBOUND_PAYLOAD,
        "MessageID": "redelivery-test-1",
        "ToFull": [
            {"Email": "a@test.com", "Name": "A", "MailboxHash": ""},
            {"Email": "b@test.com", "Name": "B", "MailboxHash": ""},
        ],
    }

    # user_a already delivered
    InboundEmail.objects.create(
        message_id=payload["MessageID"],
        user=user_a,
    )

    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp.status_code == 200
    assert InboundEmail.objects.count() == 2

    assert InboundEmail.objects.filter(user=user_b, message_id=payload["MessageID"]).exists()
