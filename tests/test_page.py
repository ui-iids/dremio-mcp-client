def test_home(client):
    response = client.get("/page")
    assert response.status_code == 200
    assert b"Lorem ipsum" in response.data
