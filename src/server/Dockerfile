FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

WORKDIR /app

# Copy only server and shared into the image (build context filtered by .dockerignore)
COPY . /app

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r /app/src/server/requirements.txt

EXPOSE 8080

CMD ["python", "-m", "server.main"]
