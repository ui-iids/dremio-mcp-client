from flask import Flask

from dremio_mcp_client.wsgi import app


def test_wsgi():
    assert isinstance(app, Flask)
    assert app.name == "dremio_mcp_client.app"
