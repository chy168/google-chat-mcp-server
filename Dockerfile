# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Poetry
RUN pip install poetry

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Expose MCP default port
EXPOSE 8080

# Set environment variables (if needed)
ENV PYTHONUNBUFFERED=1

# Start the MCP server (adjust if entrypoint is different)
CMD ["python", "server.py"]
