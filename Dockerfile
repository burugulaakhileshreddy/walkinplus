# Use a lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (if you use psycopg2 / Postgres, this helps)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . /app/

# Expose the port that Gunicorn will run on
EXPOSE 8000

# Start the app using Gunicorn and your Django WSGI module
# IMPORTANT: "walkinplus.wsgi:application" assumes your Django project folder is "walkinplus"
CMD ["gunicorn", "walkinplus.wsgi:application", "--bind", "0.0.0.0:8000"]
