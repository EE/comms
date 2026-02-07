
def test_robots_txt(client):
    response = client.get('/robots.txt')
    assert response.status_code == 200
    assert response['Content-Type'] == "text/plain"
