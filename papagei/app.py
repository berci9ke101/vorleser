"""
Web API Gateway for Vorleser OCR

Handles image uploads, saves raw images to the Blob Storage,
stores metadata in PostgreSQL, and queues OCR tasks in RabbitMQ.
"""

import uuid
import json
import requests
import pika
import psycopg2
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host='db',
        database='vorleser_db',
        user='vorleser_user',
        password='secretpassword'
    )

# Initialize database table on startup
def init_db():
    """Initializes the database table."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            blob_id VARCHAR(255) NOT NULL,
            description TEXT,
            detected_text JSONB,
            status VARCHAR(50)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Really BASIC HTML UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Vorleser OCR</title></head>
<body>
    <h2>Upload Image</h2>
    <form action="/api/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="image" required><br><br>
        <input type="text" name="description" placeholder="Short description" required><br><br>
        <button type="submit">Upload and Start OCR</button>
    </form>
</body>
</html>
"""

@app.route('/')
def index():
    """Renders the HTML form for image upload."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/upload', methods=['POST'])
def upload_image():
    """
    Handles image upload, saves to Blob Storage,
    stores metadata in PostgreSQL, and queues OCR task.
    """
    file = request.files['image']
    description = request.form.get('description', '')
    image_bytes = file.read()

    # 1. Upload to Blob Storage
    blob_id = str(uuid.uuid4()) + "_" + file.filename
    blob_url = f"http://blob-storage:5001/api/blobs/{blob_id}"
    requests.put(blob_url, data=image_bytes, timeout=10)

    # 2. Save to Postgres
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO images (blob_id, description, status) VALUES (%s, %s, %s) RETURNING id;",
        (blob_id, description, 'pending')
    )
    image_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    # 3. Send RabbitMQ message
    # Using blocking connection for simplicity
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='ocr_tasks')
    channel.basic_publish(
        exchange='',
        routing_key='ocr_tasks',
        body=json.dumps({'image_id': image_id})
    )
    connection.close()

    # Placeholder for now, will implement a status page later
    return jsonify({
        'message': 'Uploaded! The worker will process it shortly.', 
        'image_id': image_id
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
