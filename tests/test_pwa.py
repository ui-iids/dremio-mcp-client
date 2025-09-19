import json
from dremio_mcp_client.app import create_app


def test_pwa_manifest(client):
    response = client.get("/manifest.json")
    assert response.status_code == 200
    assert response.mimetype == "application/manifest+json"
    manifest = json.loads(response.data)
    assert manifest.get("name")
    assert manifest.get("start_url")


def test_pwa_sw():
    app = create_app(config_override={"SERVE_PWA": True})
    app.config.update({"TESTING": True})
    client = app.test_client()
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
