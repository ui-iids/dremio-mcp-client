from unittest import mock

import pytest
from flask_smorest import abort
from mock_alchemy.mocking import UnifiedAlchemyMagicMock

from dremio_mcp_client.models import People


class MockQuery:
    @staticmethod
    def filter_by(**kwargs):
        return MockQuery()


class MockResult:
    @staticmethod
    def first():
        return {"user_id": 1, "username": "test_user", "email": "test@example.com"}

    @staticmethod
    def all():
        return [[{"user_id": 1, "username": "test_user", "email": "test@example.com"}]]


@pytest.fixture
def mock_db(monkeypatch):
    mock_session = UnifiedAlchemyMagicMock(
        data=[
            (
                [
                    mock.call.query(People),
                ],
                [[People(user_id=1, username="test_user", email="test@example.com")]],
            ),
        ]
    )

    class MockDB:
        @staticmethod
        def get_or_404(model, user_id):
            if user_id == 1:
                return {
                    "user_id": 1,
                    "username": "test_user",
                    "email": "test@example.com",
                }
            else:
                raise abort(404)

        session = mock_session

    monkeypatch.setattr("dremio_mcp_client.api.example.v1.blueprint.db", MockDB())


def test_get_user(client, mock_db):
    response = client.get("/example/v1/user?user_id=1")
    assert response.status_code == 200
    assert response.json == {
        "user_id": 1,
        "username": "test_user",
        "email": "test@example.com",
    }


def test_delete_user(client, mock_db):
    response = client.delete("/example/v1/user", data={"user_id": 1})
    assert response.status_code == 200
    assert response.json is True


def test_get_users(client, mock_db):
    response = client.get("/example/v1/users")
    assert response.status_code == 200
    assert response.json == [
        {"user_id": 1, "username": "test_user", "email": "test@example.com"}
    ]


def test_lorem_get(client):
    response = client.get("/example/v1/lorem")
    assert response.status_code == 200
    assert response.json == {"body": "Lorem Ipsum Dolor Sit Amet"}


def test_home_rejects_post(client):
    response = client.post("/example/v1/lorem")
    assert response.status_code == 405


def test_error(client):
    response = client.get("/example/v1/NOT_AN_API")
    assert response.status_code == 404
