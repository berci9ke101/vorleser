"""
OCR Worker Service

This service continuously listens to the RabbitMQ 'ocr_tasks' queue.
When a task is received, it downloads the image from the Blob Storage,
runs optical character recognition using EasyOCR, and saves the detected
text coordinates as JSON back into the PostgreSQL database and sets the status.
"""

import json
import requests
import pika
import psycopg2
import easyocr

# Initialize EasyOCR (downloads models on first run)
print("Loading EasyOCR models...")
reader = easyocr.Reader(['en', 'hu'])

def perform_ocr(image_bytes):
    """
    Runs Optical Character Recognition on the image bytes and
    returns a JSON-serializable list of bounding boxes and text.
    """
    ocr_result = reader.readtext(image_bytes)
    bounding_boxes = []

    # Using _prob for pylint to pass, even though we don't use it
    for (bbox, text, _prob) in ocr_result:
        box_coords = [[int(coord[0]), int(coord[1])] for coord in bbox]
        bounding_boxes.append({'box': box_coords, 'text': text})

    return bounding_boxes

# Using _properties for pylint to pass, even though we don't use it
def process_task(ch, method, _properties, body):
    """
    Callback function executed when a new message is received from RabbitMQ.
    """
    data = json.loads(body)
    image_id = data['image_id']
    print(f"Processing task for image ID: {image_id}")

    # 1. Connect to PostgreSQL
    conn = psycopg2.connect(
        host='db',
        database='vorleser_db',
        user='vorleser_user',
        password='secretpassword'
    )
    cur = conn.cursor()

    # 2. Retrieve blob_id from the database
    cur.execute("SELECT blob_id FROM images WHERE id = %s;", (image_id,))
    blob_id = cur.fetchone()[0]

    # 3. Download the image bytes from the internal Blob Storage (with timeout!)
    response = requests.get(f"http://blob-storage:5001/api/blobs/{blob_id}", timeout=10)
    image_bytes = response.content

    # 4. Run Optical Character Recognition (refactored to helper function)
    bounding_boxes = perform_ocr(image_bytes)

    # 5. Save the results back to the database as JSON
    cur.execute(
        "UPDATE images SET detected_text = %s, status = 'completed' WHERE id = %s;",
        (json.dumps(bounding_boxes), image_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"Successfully processed and saved image ID: {image_id}")

    # Acknowledge the message so RabbitMQ removes it from the queue
    ch.basic_ack(delivery_tag=method.delivery_tag)


# Set up RabbitMQ connection and start consuming
# Using blocking connection for simplicity
connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
channel = connection.channel()

channel.queue_declare(queue='ocr_tasks')
channel.basic_consume(queue='ocr_tasks', on_message_callback=process_task)

print("OCR Worker started. Waiting for tasks...")
channel.start_consuming()
