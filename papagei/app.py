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
from flask import Flask, request, jsonify, render_template, redirect, abort

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

@app.route('/')
def index():
    """Renders the HTML form for image upload."""
    return render_template('index.html')

@app.route('/view/<string:blob_id>')
def view_permalink(blob_id):
    """Renders the HTML view for a specific image using UUID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM images WHERE blob_id = %s", (blob_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        abort(404)

    return render_template('view.html', blob_id=blob_id)

@app.route('/api/proxy-image/<blob_id>')
def proxy_image(blob_id):
    """Blob-storage proxy (because of CORS)."""
    r = requests.get(f"http://blob-storage:5001/api/blobs/{blob_id}", timeout=10)
    return r.content, r.status_code, {'Content-Type': 'image/jpeg'}

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
    requests.put(f"http://blob-storage:5001/api/blobs/{blob_id}", data=image_bytes, timeout=10)

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

    # Redirect to view page
    return redirect(f"/view/{blob_id}")

@app.route('/api/details/<string:blob_id>')
def image_details(blob_id):
    """Get JSON details using blob_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT description, status, blob_id, detected_text FROM images WHERE blob_id = %s",
        (blob_id,)
        )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({'error': 'Not found'}), 404

    return jsonify({
        'description': row[0],
        'status': row[1],
        'blob_url': f"/api/proxy-image/{row[2]}",
        'detected_text': row[3]
    })

@app.errorhandler(404)
def page_not_found(_e):
    """Custom 404 error handler."""
    return render_template('404.html'), 404

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
