"""
The notification service for Vorleser OCR (Klammeraffe).
Handles Telegram subscriptions.
"""

import os
import json
import threading
import requests
import pika
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '7890123456:ABC-DEF...') 

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host='vorleser-elefant',
        database='vorleser_db',
        user='vorleser_user',
        password='secretpassword'
    )

def init_db():
    """Initializes the database table."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            chat_id VARCHAR(50) UNIQUE NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_subscribers():
    """Fetches all subscribers from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM subscriptions")
        subs = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return subs
    except Exception as e:
        print(f"Error fetching subscribers: {e}")
        return []

def save_subscriber(chat_id):
    """Saves a new subscriber to the database (with duplicate protection)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO subscriptions (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING",
            (str(chat_id),)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving subscriber: {e}")
        return False

def send_telegram(chat_id, message):
    """Sends a message via Telegram API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if not response.ok:
            print(f"Telegram API rejected: {response.status_code} - {response.text}")
        else:
            print(f"Message sent successfully to: {chat_id}")
    except Exception as e:
        print(f"Network error while sending Telegram message: {e}")

def get_all_historical_data():
    """Fetches all historical OCR results from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT description, detected_text, blob_id FROM images WHERE status = 'completed' ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

def format_ocr_text(raw_data):
    """Formats the OCR JSON list into a readable string."""
    try:
        # If it's already a string, try to parse it as JSON; if it's already a dict/list, use it directly
        data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        
        # If it's a list of dicts, extract the 'text' field from each item and join them; otherwise, return the raw string
        if isinstance(data, list):
            return " ".join([item.get('text', '') for item in data])
        return str(raw_data)
    except:
        return str(raw_data)

# RabbitMQ Listener Logic

def start_rabbit_listener():
    """RabbitMQ listener."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('vorleser-brieftaube'))
        channel = connection.channel()

        channel.exchange_declare(exchange='image_notifications', exchange_type='fanout')
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='image_notifications', queue=queue_name)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                # Send Telegram notifications to all subscribers
                current_subs = get_subscribers()
                if current_subs:
                    raw_text = data.get('text', '')
                    readable_text = format_ocr_text(raw_text)
                    clean_text = readable_text[:3000] + "..." if len(readable_text) > 3000 else readable_text

                    msg = (f"<b>🔔 New OCR Result!</b>\n\n"
                           f"<b>Description:</b> {data.get('desc', 'No description')}\n"
                           f"<b>Text:</b>\n<i>{clean_text}</i>")

                    for chat_id in current_subs:
                        threading.Thread(target=send_telegram, args=(chat_id, msg), daemon=True).start()
            except Exception as e:
                print(f"Error in callback: {e}")

        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        print("Klammeraffe is listening for RabbitMQ messages...")
        channel.start_consuming()
    except Exception as e:
        print(f"RabbitMQ connection error: {e}")

# API Endpoints

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    chat_id = request.json.get('chat_id')
    if not chat_id:
        return jsonify({"error": "Missing chat_id"}), 400

    if save_subscriber(chat_id):
        history = get_all_historical_data()
        if history:
            # Shortened header
            history_msg = "<b>📂 History Sync (Last 5):</b>\n\n"
            
            # Just the Last 5 entries, with cleaned and shortened text
            for row in history[:5]:
                # Clean and shorten the OCR text for display
                raw_text = format_ocr_text(row[1])
                short_text = (raw_text[:60] + "...") if len(raw_text) > 60 else raw_text
                
                line = f"• {row[0]}: <i>{short_text}</i>\n"
                
                # Check if adding this line would exceed Telegram's message limit (4000 chars)
                if len(history_msg) + len(line) < 4000:
                    history_msg += line
            
            send_telegram(chat_id, history_msg)
        else:
            send_telegram(chat_id, "Subscribed! No history yet.")
            
        return jsonify({"status": "subscribed"}), 200
    return jsonify({"error": "Database error"}), 500

@app.route('/api/history', methods=['GET'])
def history_api():
    """Dashboard historical data endpoint."""
    data = get_all_historical_data()
    formatted = [{"desc": r[0], "text": r[1], "blob_id": r[2]} for r in data]
    return jsonify(formatted)

if __name__ == '__main__':
    # Create the database table if it doesn't exist
    init_db()
    # Start RabbitMQ listener in a separate thread
    threading.Thread(target=start_rabbit_listener, daemon=True).start()
    app.run(host='0.0.0.0', port=5002)