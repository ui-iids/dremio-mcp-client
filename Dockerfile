# We use a separate image to build the project.
# This ensures that build dependencies from Python are not included.
# Build dependencies within the project will still come through.
FROM python:3.13 AS builder

# This project uses UV as its builder.
# Note: This might stop working in a future version of Ubuntu due to python global installs being forbidden.
RUN pip install uv

# Change working directory to `/app`
WORKDIR /app

# Copy necessary files to build dependencies
COPY pyproject.toml ./
RUN touch README.md

# Install with only the dependencies to serve the application
RUN uv sync --no-default-groups --group serve

# Use a slim image for runtime
FROM python:3.13-slim AS runtime

WORKDIR /app

RUN addgroup --gid 1001 --system gunicorn
RUN adduser --system gunicorn --uid 1001 --gid 1001

# Copy this early, so changes in the project or configuration don't rebuild
COPY pyproject.toml .

# Set the virtual environment manually
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Setup python env vars
ENV PYTHONUNBUFFERED=1

# Copy the virtual environment
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copy project files
COPY dremio_mcp_client dremio_mcp_client

# Copy gunicorn configuration and project description
COPY gunicorn.conf.py .

# Set permissions for the application and database
RUN mkdir instance
RUN chgrp gunicorn -R .
RUN chmod 750 -R .
# Local SQLite Database directory needs write
RUN chmod 770 instance

USER gunicorn

EXPOSE 8000

ENV GUNICORN_WORKERS=1 

ENTRYPOINT ["gunicorn"]