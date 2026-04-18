FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# OKD permission fix for storage directory
RUN mkdir -p /app/storage && \
    chgrp -R 0 /app/storage && \
    chmod -R g=u /app/storage

CMD ["python", "app.py"]
