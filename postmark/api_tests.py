from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from postmark.models import InboundEmail
from users.models import User


@pytest.fixture(name="user")
def user_fixture(db):
    return User.objects.create_user(
        username="inboxuser", password="testpass",
        email="sender@example.com",
    )


@pytest.fixture(name="other_user")
def other_user_fixture(db):
    return User.objects.create_user(username="otheruser", password="testpass")


@pytest.fixture(name="client")
def api_client_fixture(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture(name="email_in_inbox")
def email_in_inbox_fixture(user):
    return InboundEmail.objects.create(
        message_id="inbox-1",
        from_email="sender@example.com",
        subject="Hello",
        user=user,
    )


# ── List ────────────────────────────────────────────────────────────


URL = "/api/inbound-emails/"


def test_reverse_url():
    assert reverse("inbound-email-list") == URL


@pytest.mark.django_db
def test_inbox_list_returns_own_emails(client, email_in_inbox):
    resp = client.get(URL)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == str(email_in_inbox.pk)


@pytest.mark.django_db
def test_inbox_list_excludes_other_users_emails(client, other_user):
    InboundEmail.objects.create(
        message_id="other-1",
        from_email="x@example.com",
        subject="Not mine",
        user=other_user,
    )
    resp = client.get(URL)
    assert resp.json()["results"] == []


@pytest.mark.django_db
def test_inbox_list_unauthenticated(db):
    resp = APIClient().get(URL)
    assert resp.status_code == 401


# ── Retrieve ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_inbox_retrieve(client, email_in_inbox):
    resp = client.get(f"{URL}{email_in_inbox.pk}/")
    assert resp.status_code == 200
    assert resp.json()["subject"] == "Hello"


@pytest.mark.django_db
def test_inbox_retrieve_includes_headers(client, user):
    headers_data = [
        {"Name": "X-Spam-Tests", "Value": "DKIM_SIGNED,DKIM_VALID,SPF_PASS"},
        {"Name": "X-Spam-Score", "Value": "-0.1"},
    ]
    email = InboundEmail.objects.create(
        message_id="headers-1",
        from_email="sender@example.com",
        subject="With headers",
        user=user,
        headers=headers_data,
    )
    resp = client.get(f"{URL}{email.pk}/")
    assert resp.status_code == 200
    assert resp.json()["headers"] == headers_data


@pytest.mark.django_db
def test_inbox_retrieve_headers_empty_by_default(client, email_in_inbox):
    resp = client.get(f"{URL}{email_in_inbox.pk}/")
    assert resp.status_code == 200
    assert resp.json()["headers"] == []


@pytest.mark.django_db
def test_inbox_retrieve_other_users_email_404(client, other_user):
    other_email = InboundEmail.objects.create(
        message_id="other-2",
        from_email="x@example.com",
        user=other_user,
    )
    resp = client.get(f"{URL}{other_email.pk}/")
    assert resp.status_code == 404


# ── Delete ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_inbox_delete_own_email(client, email_in_inbox):
    resp = client.delete(f"{URL}{email_in_inbox.pk}/")
    assert resp.status_code == 204
    assert not InboundEmail.objects.filter(pk=email_in_inbox.pk).exists()


@pytest.mark.django_db
def test_inbox_delete_other_users_email_404(client, other_user):
    other_email = InboundEmail.objects.create(
        message_id="other-3",
        from_email="x@example.com",
        user=other_user,
    )
    resp = client.delete(f"{URL}{other_email.pk}/")
    assert resp.status_code == 404
    assert InboundEmail.objects.filter(pk=other_email.pk).exists()


@pytest.mark.django_db
def test_inbox_delete_unauthenticated(email_in_inbox):
    resp = APIClient().delete(f"{URL}{email_in_inbox.pk}/")
    assert resp.status_code == 401
    assert InboundEmail.objects.filter(pk=email_in_inbox.pk).exists()


# ── Write-protection ────────────────────────────────────────────────


@pytest.mark.django_db
def test_inbox_post_not_allowed(client):
    resp = client.post(URL, data={})
    assert resp.status_code == 405


@pytest.mark.django_db
def test_inbox_put_not_allowed(client, email_in_inbox):
    resp = client.put(f"{URL}{email_in_inbox.pk}/", data={})
    assert resp.status_code == 405


# ════════════════════════════════════════════════════════════════════
# Outbound messages
# ════════════════════════════════════════════════════════════════════

OUTBOUND_URL = "/api/outbound-messages/"
SENDER = "sender@example.com"


@pytest.fixture(name="send_settings")
def send_settings_fixture(settings):
    settings.POSTMARK_SERVER_TOKEN = "test-server-token"


def _postmark_ok(to="receiver@example.com"):
    """Fake successful Postmark response."""
    return type("Resp", (), {
        "status_code": 200,
        "json": lambda self: {
            "ErrorCode": 0,
            "Message": "OK",
            "MessageID": "abc-123",
            "SubmittedAt": "2026-01-01T00:00:00Z",
            "To": to,
        },
    })()


def _valid_payload(**overrides):
    data = {
        "from_email": SENDER,
        "to": "receiver@example.com",
        "subject": "Hi",
        "text_body": "Hello",
    }
    data.update(overrides)
    return data


def test_outbound_url():
    assert reverse("outbound-message-list") == OUTBOUND_URL


# ── Create (send) ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_send_email_success(client, send_settings):
    with patch("postmark.api.httpx.post", return_value=_postmark_ok()) as mock:
        resp = client.post(OUTBOUND_URL, _valid_payload(), format="json")

    assert resp.status_code == 200
    assert resp.json()["MessageID"] == "abc-123"

    call_kwargs = mock.call_args
    assert call_kwargs[1]["headers"]["X-Postmark-Server-Token"] == "test-server-token"
    payload = call_kwargs[1]["json"]
    assert payload["From"] == SENDER
    assert payload["To"] == "receiver@example.com"
    assert payload["TextBody"] == "Hello"


@pytest.mark.django_db
def test_send_email_html_only(client, send_settings):
    with patch("postmark.api.httpx.post", return_value=_postmark_ok()) as mock:
        resp = client.post(
            OUTBOUND_URL,
            _valid_payload(text_body="", html_body="<b>Hi</b>"),
            format="json",
        )

    assert resp.status_code == 200
    payload = mock.call_args[1]["json"]
    assert payload["HtmlBody"] == "<b>Hi</b>"
    assert "TextBody" not in payload


@pytest.mark.django_db
def test_send_email_optional_fields(client, send_settings):
    with patch("postmark.api.httpx.post", return_value=_postmark_ok()) as mock:
        resp = client.post(
            OUTBOUND_URL,
            _valid_payload(
                cc="cc@example.com",
                bcc="bcc@example.com",
                reply_to="reply@example.com",
                tag="welcome",
                track_opens=True,
                track_links="HtmlOnly",
                metadata={"color": "blue"},
                message_stream="broadcasts",
            ),
            format="json",
        )

    assert resp.status_code == 200
    payload = mock.call_args[1]["json"]
    assert payload["Cc"] == "cc@example.com"
    assert payload["Bcc"] == "bcc@example.com"
    assert payload["ReplyTo"] == "reply@example.com"
    assert payload["Tag"] == "welcome"
    assert payload["TrackOpens"] is True
    assert payload["TrackLinks"] == "HtmlOnly"
    assert payload["Metadata"] == {"color": "blue"}
    assert payload["MessageStream"] == "broadcasts"


@pytest.mark.django_db
def test_send_email_wrong_from(client, send_settings):
    resp = client.post(
        OUTBOUND_URL,
        _valid_payload(from_email="evil@hacker.com"),
        format="json",
    )
    assert resp.status_code == 400
    assert "from_email" in resp.json()
    assert SENDER in resp.json()["from_email"][0]


@pytest.mark.django_db
def test_send_email_wrong_from_with_name(client, send_settings):
    resp = client.post(
        OUTBOUND_URL,
        _valid_payload(from_email="Attacker <evil@hacker.com>"),
        format="json",
    )
    assert resp.status_code == 400
    assert "from_email" in resp.json()


@pytest.mark.django_db
def test_send_email_valid_from_with_name(client, send_settings):
    with patch("postmark.api.httpx.post", return_value=_postmark_ok()):
        resp = client.post(
            OUTBOUND_URL,
            _valid_payload(from_email=f"Sales Team <{SENDER}>"),
            format="json",
        )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_send_email_no_body(client, send_settings):
    resp = client.post(
        OUTBOUND_URL,
        _valid_payload(text_body="", html_body=""),
        format="json",
    )
    assert resp.status_code == 400
    assert "non_field_errors" in resp.json()


@pytest.mark.django_db
def test_send_email_missing_to(client, send_settings):
    payload = _valid_payload()
    del payload["to"]
    resp = client.post(OUTBOUND_URL, payload, format="json")
    assert resp.status_code == 400
    assert "to" in resp.json()


@pytest.mark.django_db
def test_send_email_unauthenticated(db):
    resp = APIClient().post(OUTBOUND_URL, _valid_payload(), format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_send_email_postmark_error_forwarded(client, send_settings):
    error_resp = type("Resp", (), {
        "status_code": 422,
        "json": lambda self: {
            "ErrorCode": 300,
            "Message": "Invalid 'To' address.",
        },
    })()

    with patch("postmark.api.httpx.post", return_value=error_resp):
        resp = client.post(OUTBOUND_URL, _valid_payload(), format="json")

    assert resp.status_code == 422
    assert resp.json()["ErrorCode"] == 300


@pytest.mark.django_db
def test_send_email_user_without_email(send_settings, db):
    no_email_user = User.objects.create_user(
        username="noemail", password="testpass", email="",
    )
    c = APIClient()
    c.force_authenticate(user=no_email_user)
    resp = c.post(OUTBOUND_URL, _valid_payload(), format="json")
    assert resp.status_code == 400
    assert "no email" in resp.json()["from_email"][0].lower()


# ── List (search) ───────────────────────────────────────────────────


def _postmark_list_response():
    return type("Resp", (), {
        "status_code": 200,
        "json": lambda self: {
            "TotalCount": 1,
            "Messages": [
                {
                    "MessageID": "msg-1",
                    "From": "sender@example.com",
                    "To": [{"Email": "r@example.com", "Name": None}],
                    "Subject": "Hi",
                    "Status": "Sent",
                    "ReceivedAt": "2026-01-01T00:00:00Z",
                    "MessageStream": "outbound",
                },
            ],
        },
    })()


@pytest.mark.django_db
def test_list_outbound_messages(client, send_settings):
    with patch("postmark.api.httpx.get", return_value=_postmark_list_response()) as mock:
        resp = client.get(OUTBOUND_URL)

    assert resp.status_code == 200
    assert resp.json()["TotalCount"] == 1
    assert len(resp.json()["Messages"]) == 1

    call_kwargs = mock.call_args
    assert call_kwargs[1]["params"]["count"] == "20"
    assert call_kwargs[1]["params"]["offset"] == "0"
    # fromemail is always forced to the caller's email
    assert call_kwargs[1]["params"]["fromemail"] == SENDER
    assert call_kwargs[1]["headers"]["X-Postmark-Server-Token"] == "test-server-token"


@pytest.mark.django_db
def test_list_outbound_messages_passes_query_params(client, send_settings):
    with patch("postmark.api.httpx.get", return_value=_postmark_list_response()) as mock:
        resp = client.get(
            OUTBOUND_URL,
            {"count": "50", "offset": "10", "tag": "welcome", "status": "sent"},
        )

    assert resp.status_code == 200
    params = mock.call_args[1]["params"]
    assert params["count"] == "50"
    assert params["offset"] == "10"
    assert params["tag"] == "welcome"
    assert params["status"] == "sent"
    # fromemail is always forced, not user-controllable
    assert params["fromemail"] == SENDER


@pytest.mark.django_db
def test_list_outbound_messages_cannot_override_fromemail(client, send_settings):
    with patch("postmark.api.httpx.get", return_value=_postmark_list_response()) as mock:
        client.get(OUTBOUND_URL, {"fromemail": "other@example.com"})

    # Caller tried to sneak in a different fromemail, but it gets overridden
    assert mock.call_args[1]["params"]["fromemail"] == SENDER


@pytest.mark.django_db
def test_list_outbound_messages_unauthenticated(db):
    resp = APIClient().get(OUTBOUND_URL)
    assert resp.status_code == 401


# ── Retrieve (details) ──────────────────────────────────────────────


def _postmark_detail_response():
    return type("Resp", (), {
        "status_code": 200,
        "json": lambda self: {
            "MessageID": "msg-1",
            "From": "sender@example.com",
            "To": [{"Email": "r@example.com", "Name": None}],
            "Subject": "Hi",
            "TextBody": "Hello",
            "HtmlBody": "",
            "Status": "Sent",
            "ReceivedAt": "2026-01-01T00:00:00Z",
            "MessageStream": "outbound",
            "MessageEvents": [],
        },
    })()


@pytest.mark.django_db
def test_retrieve_outbound_message(client, send_settings):
    with patch("postmark.api.httpx.get", return_value=_postmark_detail_response()) as mock:
        resp = client.get(f"{OUTBOUND_URL}msg-1/")

    assert resp.status_code == 200
    assert resp.json()["MessageID"] == "msg-1"
    assert resp.json()["Subject"] == "Hi"

    url_called = mock.call_args[0][0]
    assert "/messages/outbound/msg-1/details" in url_called


@pytest.mark.django_db
def test_retrieve_outbound_message_unauthenticated(db):
    resp = APIClient().get(f"{OUTBOUND_URL}msg-1/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_retrieve_outbound_message_not_found(client, send_settings):
    not_found_resp = type("Resp", (), {
        "status_code": 422,
        "json": lambda self: {
            "ErrorCode": 701,
            "Message": "Message not found.",
        },
    })()
    with patch("postmark.api.httpx.get", return_value=not_found_resp):
        resp = client.get(f"{OUTBOUND_URL}nonexistent/")

    assert resp.status_code == 422
    assert resp.json()["ErrorCode"] == 701


@pytest.mark.django_db
def test_retrieve_outbound_message_other_user_is_404(client, send_settings):
    """A message sent by someone else should look like a 404."""
    other_user_msg = type("Resp", (), {
        "status_code": 200,
        "json": lambda self: {
            "MessageID": "msg-other",
            "From": "\"Evil\" <other@example.com>",
            "To": [{"Email": "r@example.com", "Name": None}],
            "Subject": "Secret",
            "TextBody": "You should not see this.",
            "Status": "Sent",
            "MessageStream": "outbound",
            "MessageEvents": [],
        },
    })()
    with patch("postmark.api.httpx.get", return_value=other_user_msg):
        resp = client.get(f"{OUTBOUND_URL}msg-other/")

    assert resp.status_code == 404
