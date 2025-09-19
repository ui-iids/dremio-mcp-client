import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.append(str(Path(__file__).absolute().parent.parent))
from dremio_mcp_client import create_app


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )

    # other setup can go here

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def runner(app: Flask):
    return app.test_cli_runner()
