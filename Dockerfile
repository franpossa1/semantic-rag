FROM python:3.13-slim-bullseye

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy the application into the container.
WORKDIR /app
COPY . /app

# Install the application dependencies.
RUN uv sync --locked --no-cache

# Run the application.
EXPOSE 8000
CMD ["/app/.venv/bin/hypercorn", "main:app", "--bind", "0.0.0.0:8000"]
