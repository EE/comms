import pytest


@pytest.mark.django_db
def test_admin_changelist(admin_client):
    resp = admin_client.get("/admin/postmark/inboundemail/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_no_add(admin_client):
    resp = admin_client.get("/admin/postmark/inboundemail/add/")
    assert resp.status_code == 403
