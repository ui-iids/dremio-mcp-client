# dremio_mcp_client

dremio_mcp_client created by ViaJables

## Install

This package intends `uv` as its build system and package manager, but is likely compatible with `pip`.

To install the project, install `uv` through your local package manager, install script, or `pip`.

Then run

```
uv sync
```

in the root directory.

## Run

To run the project as a developer, run:

```bash
uv run flask --app dremio_mcp_client run --debug
```

To run the project as a standalone server, run:

```bash
gunicorn
```

To run the project in a container, after installing docker, run:

```bash
docker build -t dremio_mcp_client -f Containerfile .
docker run -d --name dremio_mcp_client -p 8005:8000 dremio_mcp_client
python -m webbrowser http://localhost:8005
```

And to delete, run:

```bash
docker stop dremio_mcp_client
docker container rm dremio_mcp_client
docker image rm dremio_mcp_client
```

## Deploy

## Updating

## Authors

Clinton Bradford, cbradford@uidaho.edu

Based on the [IIDS Flask Cookiecutter](https://github.com/ui-iids/flask-cookiecutter)
