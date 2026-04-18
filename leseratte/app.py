"""
OCR Worker Service with Health Endpoint
"""

import json
import threading
import requests
import pika
import psycopg2
import easyocr
from flask import Flask

# Globals
IS_READY = False
READER = None

# Health check setup
health_app = Flask(__name__)

@health_app.route('/health')
def health():
    """Health check endpoint for Docker. Returns 200 if ready, 503 otherwise."""
    if (READER is not None) and IS_READY:
        return "Ready", 200
    return "Initializing models...", 503

def run_health_server():
    """Runs a minimal flask server for Docker health checks."""
    health_app.run(host='0.0.0.0', port=8080)

def perform_ocr(image_bytes):
    """
    Runs Optical Character Recognition on the image bytes and
    returns a JSON-serializable list of bounding boxes and text.
    """
    ocr_result = READER.readtext(image_bytes)
    bounding_boxes = []
    for (bbox, text, _prob) in ocr_result:
        box_coords = [[int(coord[0]), int(coord[1])] for coord in bbox]
        bounding_boxes.append({'box': box_coords, 'text': text})
    return bounding_boxes

def process_task(ch, method, _properties, body):
    """
    Callback function executed when a new message is received from RabbitMQ.
    """
    data = json.loads(body)
    image_id = data['image_id']
    print(f"Processing task for image ID: {image_id}")

    conn = psycopg2.connect(
        host='db',
        database='vorleser_db',
        user='vorleser_user',
        password='secretpassword'
    )
    cur = conn.cursor()

    # Retrieve blob_id from the database
    try:
        cur.execute("SELECT blob_id FROM images WHERE id = %s;", (image_id,))
        blob_id = cur.fetchone()[0]

        response = requests.get(f"http://blob-storage:5001/api/blobs/{blob_id}", timeout=10)
        image_bytes = response.content

        bounding_boxes = perform_ocr(image_bytes)

        cur.execute(
            "UPDATE images SET detected_text = %s, status = 'completed' WHERE id = %s;",
            (json.dumps(bounding_boxes), image_id)
        )
        conn.commit()
        print(f"Successfully processed image ID: {image_id}")
    finally:
        cur.close()
        conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    """Initializes models and starts consuming RabbitMQ tasks."""
    global READER, IS_READY # pylint: disable=global-statement

    print("Loading EasyOCR models...")
    READER = easyocr.Reader(['en', 'hu'])

    # Indicate to health check that we are fully operational
    IS_READY = True
    print("Models loaded. OCR Worker ready for tasks.")

    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='ocr_tasks')
    channel.basic_consume(queue='ocr_tasks', on_message_callback=process_task)

    channel.start_consuming()

if __name__ == '__main__':
    # Start health server in a background thread
    threading.Thread(target=run_health_server, daemon=True).start()
    # Run the main worker logic
    start_worker()
