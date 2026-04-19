FROM python:3.9-slim
WORKDIR /app

# For correct logging in Docker
ENV PYTHONUNBUFFERED=1

# Configure apt and install packages
RUN apt-get update -y && \
    apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-dev \
    curl \
    # cleanup
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists

# OKD permission fix for models directory
RUN mkdir -p /app/models && chmod -R 775 /app && chgrp -R 0 /app
ENV HOME=/app
ENV EASYOCR_MODULE_PATH=/app/models

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt
RUN python -c "import easyocr; easyocr.Reader(['en', 'hu'], model_storage_directory='/app/models')"

COPY . .

CMD ["python", "app.py"]