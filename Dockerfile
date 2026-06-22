FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY cladecanvas ./cladecanvas

EXPOSE 8080

CMD ["uvicorn", "cladecanvas.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
