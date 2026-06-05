FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# OS deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY scripts /app/scripts
COPY pytest.ini /app/pytest.ini

ENV STORAGE_DIR=/app/storage
RUN mkdir -p /app/storage/images /app/storage/recon /app/storage/heatmaps

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
