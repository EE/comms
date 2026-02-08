import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from postmark.models import InboundEmail
from users.models import User


@pytest.fixture(name="user")
def user_fixture(db):
    return User.objects.create_user(username="inboxuser", password="testpass")


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
