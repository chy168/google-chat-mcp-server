# Use official Python image
FROM python:3.13-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies only (cached layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application
COPY . .

# Install the project
RUN uv sync --frozen --no-dev

# Expose MCP default port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Start the MCP server
ENTRYPOINT ["uv", "run", "server.py"]
