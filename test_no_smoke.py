import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_admin_root(admin_client):
    response = admin_client.get(reverse('admin:index'))
    assert response.status_code == 200
