def test_api_root(api_user_client):
    response = api_user_client.get('/api/')
    assert response.status_code == 200
