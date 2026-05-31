FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

WORKDIR /app

# Copy only server and shared into the image (build context filtered by .dockerignore)
COPY . /app

# Install minimal runtime dependencies; if you provide requirements.txt it will be installed too
RUN pip install --no-cache-dir aiohttp python-socketio && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

EXPOSE 8080

CMD ["python", "-m", "server.main"]
