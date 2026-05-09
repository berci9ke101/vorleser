FROM python:3.9-slim
WORKDIR /app

# For correct logging in Docker
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]