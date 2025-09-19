from os import environ

wsgi_app = "dremio_mcp_client.wsgi:app"
bind = "0.0.0.0:8000"
workers = int(environ.get("GUNICORN_WORKERS", 1))
