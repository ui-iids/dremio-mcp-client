from flask import Flask

from project_name.wsgi import app


def test_wsgi():
    assert isinstance(app, Flask)
    assert app.name == "project_name.app"
