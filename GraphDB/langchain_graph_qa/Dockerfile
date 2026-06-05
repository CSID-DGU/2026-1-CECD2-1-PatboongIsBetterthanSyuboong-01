FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5001 8001
CMD ["python", "-m", "uvicorn", "certificate_api:app", "--host", "0.0.0.0", "--port", "5001"]
