import pytest
from rest_framework.test import APIClient

from users.models import User


@pytest.fixture(name='user')
def user_fixture(db):
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.fixture(name='api_user_client')
def api_user_client_fixture(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
