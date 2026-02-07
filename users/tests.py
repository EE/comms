import pytest
from django.urls import reverse
from knox.models import AuthToken


@pytest.mark.django_db
def test_admin_create_token(admin_client, admin_user):
    url = reverse("admin:knox_authtoken_add")
    response = admin_client.post(url, {
        "user": admin_user.pk,
        "expiry_0": "2026-03-01",
        "expiry_1": "00:00:00",
    })

    assert response.status_code == 200
    assert b"Token created" in response.content
    # the raw token is displayed exactly once on the response page
    assert b"raw-token" in response.content

    # a token row was persisted for this user
    assert AuthToken.objects.filter(user=admin_user).count() == 1


@pytest.mark.django_db
def test_admin_view_token(admin_client, admin_user):
    instance, _raw = AuthToken.objects.create(user=admin_user)
    url = reverse("admin:knox_authtoken_change", args=[instance.pk])
    response = admin_client.get(url)

    assert response.status_code == 200
    assert admin_user.username.encode() in response.content
