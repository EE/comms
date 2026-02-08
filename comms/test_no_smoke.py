
def test_robots_txt(client):
    response = client.get('/robots.txt')
    assert response.status_code == 200
    assert response['Content-Type'] == "text/plain"


def test_skill_md(client):
    response = client.get('/skill.md')
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode()
    assert "POST /api/outbound-messages/" in body
    assert "GET /api/outbound-messages/" in body
    assert "GET /api/inbound-emails/" in body
