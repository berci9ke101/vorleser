"""
A simple Flask-based REST API for storing, retrieving, and deleting
binary blobs (e.g., images) on the server filesystem.
Endpoints:
    PUT   /api/blobs/<blob_id>    - Uploads and saves a blob with the given ID.
    GET   /api/blobs/<blob_id>    - Retrieves and downloads the blob with the given ID.
    DELETE /api/blobs/<blob_id>   - Deletes the blob with the given ID.
Configuration:
    STORAGE_DIR: Directory path where blobs are stored. Ensured to exist at startup.
Usage:
    Run the app and interact with the endpoints to manage blobs by their IDs.
"""

import os
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def get_storage_dir():
    """
    Returns the storage directory path.

    This function retrieves the storage directory path from the 'STORAGE_DIR' environment variable.
    If the environment variable is not set, it defaults to '/app/data'.

    Returns:
        str: The path to the storage directory.
    """
    return os.getenv('STORAGE_DIR', '/app/data')

STORAGE_DIR = get_storage_dir()

# At start we make sure that STORAGE_DIR exists
os.makedirs(STORAGE_DIR, exist_ok=True)

@app.route('/api/blobs/<blob_id>', methods=['PUT'])
def upload_blob(blob_id):
    """Save image into storage (client sends the data)."""
    storage_dir = get_storage_dir()
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, blob_id)
    with open(file_path, 'wb') as f:
        f.write(request.data)
    return jsonify({'message': 'Saved successfully', 'blob_id': blob_id}), 201

@app.route('/api/blobs/<blob_id>', methods=['GET'])
def get_blob(blob_id):
    """Download image (client requests the date)."""
    storage_dir = get_storage_dir()
    file_path = os.path.join(storage_dir, blob_id)
    if not os.path.exists(file_path):
        return jsonify({'error': 'No such file'}), 404
    return send_file(file_path)

@app.route('/api/blobs/<blob_id>', methods=['DELETE'])
def delete_blob(blob_id):
    """Delete image (client requests image removal)."""
    storage_dir = get_storage_dir()
    file_path = os.path.join(storage_dir, blob_id)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'message': 'Deleted successfully'}), 200
    return jsonify({'error': 'No such file'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
