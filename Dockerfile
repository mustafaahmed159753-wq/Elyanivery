# Elyanivery — Railway Deployment Dockerfile
# PostgreSQL version — no ODBC drivers needed!

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p static/uploads

EXPOSE 8080
CMD ["python", "server.py"]
