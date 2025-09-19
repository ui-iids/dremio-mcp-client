from tempfile import NamedTemporaryFile

from flask import Flask
from sassutils.wsgi import SassMiddleware

from dremio_mcp_client import create_app


def test_create_app_handles_no_file():
    app = create_app("nonexistent.file")
    app.config.update({"TESTING": True})
    assert isinstance(app, Flask)


def test_create_app_handles_config():
    with NamedTemporaryFile() as config_file:
        config_file.write(b"PYTEST_EXAMPLE_CONFIG=true\nOVERRIDED_PARAM=0")
        config_file.flush()
        app = create_app(config_file.name, {"OVERRIDED_PARAM": 1, "OTHER_PARAM": 2})
        app.config.update({"TESTING": True})
        assert isinstance(app, Flask)
        assert app.config.get("PYTEST_EXAMPLE_CONFIG")
        assert app.config.get("OTHER_PARAM") == 2
        assert app.config.get("OVERRIDED_PARAM") == 1


def test_create_app_installs_sass_middleware():
    live_app = create_app()
    assert not isinstance(live_app.wsgi_app, SassMiddleware)
    debug_app = create_app(config_override={"DEBUG": True})
    assert isinstance(debug_app.wsgi_app, SassMiddleware)
