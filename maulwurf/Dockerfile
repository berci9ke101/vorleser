FROM python:3.9-slim
WORKDIR /app

# For correct logging in Docker
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# OKD permission fix for storage directory
RUN mkdir -p /app/data && \
    chgrp -R 0 /app/data && \
    chmod -R g=u /app/data

CMD ["python", "app.py"]
