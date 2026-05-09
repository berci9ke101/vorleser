"""
The notification service for Vorleser OCR (Klammeraffe).
Handles Telegram subscriptions and real-time WebSocket updates.
"""

import os
import json
import threading
import requests
import pika
import psycopg2
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

app = Flask(__name__)
# SocketIO instance with CORS allowed for all origins (for simplicity)
socketio = SocketIO(app, cors_allowed_origins="*")

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
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram API error: {e}")

def get_all_historical_data():
    """Fetches all historical OCR results from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT description, detected_text FROM images WHERE status = 'completed' ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

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
                # 1. Update Dashboard in real-time
                socketio.emit('update_dashboard', data)

                # 2. Send Telegram notifications to all subscribers
                current_subs = get_subscribers()
                if current_subs:
                    raw_text = data.get('text', '')
                    clean_text = raw_text[:3500] + "..." if len(raw_text) > 3500 else raw_text
                    
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
    """Saves a new subscriber to the database."""
    data = request.json
    chat_id = data.get('chat_id')
    
    if not chat_id:
        return jsonify({"error": "Chat ID is missing"}), 400

    if save_subscriber(chat_id):
        # If subscription is successful, send historical data to the new subscriber
        history = get_all_historical_data()
        if history:
            history_msg = "<b>📂 Historical Analyses Synchronization:</b>\n\n"
            for row in history[:10]: # Only send the last 10 entries to avoid overwhelming the user
                history_msg += f"• {row[0]}: <i>{row[1][:50]}...</i>\n"
            send_telegram(chat_id, history_msg)
        else:
            send_telegram(chat_id, "Successful subscription! There is no previous data available.")
        
        return jsonify({"status": "subscribed"}), 200
    else:
        return jsonify({"error": "Database error"}), 500

@app.route('/api/history', methods=['GET'])
def history_api():
    """Dashboard historical data endpoint."""
    data = get_all_historical_data()
    formatted = [{"desc": r[0], "text": r[1]} for r in data]
    return jsonify(formatted)

if __name__ == '__main__':
    # Create the database table if it doesn't exist
    init_db()
    # Start RabbitMQ listener in a separate thread
    threading.Thread(target=start_rabbit_listener, daemon=True).start()
    # Start the Flask app with SocketIO support
    socketio.run(app, host='0.0.0.0', port=5002, allow_unsafe_werkzeug=True)