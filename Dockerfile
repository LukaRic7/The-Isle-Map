FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy only the server folder into the image
COPY server/ ./server/

# If the server has its own requirements file, install from it.
# This avoids installing an invalid root requirements.txt that can break builds.
RUN if [ -f /app/server/requirements.txt ]; then pip install --no-cache-dir -r /app/server/requirements.txt; fi

WORKDIR /app/server

# Default port (override with environment variable)
ENV PORT=56556
EXPOSE ${PORT}

# Run the server main file
CMD ["python", "main.py"]
