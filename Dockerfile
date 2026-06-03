# Elyanivery — Railway Deployment Dockerfile
# Installs ODBC Driver 18 for SQL Server on Linux, then runs the Python server

FROM python:3.11-slim

# Install dependencies, then Microsoft ODBC Driver 18
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    unixodbc-dev \
    apt-transport-https \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
       -o /etc/apt/sources.list.d/mssql-release.list \
    && sed -i 's|signed-by=/usr/share/keyrings/microsoft-prod.gpg|signed-by=/usr/share/keyrings/microsoft-prod.gpg|g' /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create uploads directory
RUN mkdir -p static/uploads

# Expose the port (Railway sets PORT env var)
EXPOSE 8080

# Start the server
CMD ["python", "server.py"]
