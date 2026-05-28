FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy only the server folder into the image
COPY server/ ./server/

# Install requirements if present at repo root (or create server/requirements.txt and adjust)
COPY requirements.txt .
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

WORKDIR /app/server

# Default port (override with environment variable)
ENV PORT=56556
EXPOSE ${PORT}

# Run the server main file
CMD ["python", "main.py"]
