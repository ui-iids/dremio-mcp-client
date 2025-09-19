from flask import abort


def test_not_found(client):
    response = client.get("/page_that_does_not_exist")
    assert response.status_code == 404
    assert (
        b'<h1 id="error-message" class="404-error-message">404 Error</h1>'
        in response.data
    )


def test_server_error(app, client):
    @app.route("/throwserror")
    def throws_error():
        abort(500)

    response = client.get("/throwserror")
    assert response.status_code == 500
    assert (
        b'<h1 id="error-message" class="generic-error-message">Error</h1>'
        in response.data
    )
