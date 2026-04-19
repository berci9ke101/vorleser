import os
import tempfile
import unittest
import shutil
import warnings
from app import app

# Suppress ResourceWarning for unclosed files in tests
warnings.simplefilter("ignore", ResourceWarning)

class TestBlobAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        # Set STORAGE_DIR for testing
        os.environ['STORAGE_DIR'] = self.temp_dir

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
        # Remove the env var
        if 'STORAGE_DIR' in os.environ:
            del os.environ['STORAGE_DIR']

    def test_upload_blob(self):
        blob_id = 'test_blob'
        data = b'Hello, World!'
        response = self.app.put('/api/blobs/' + blob_id, data=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn('Saved successfully', response.get_json()['message'])

        # Check if file exists
        file_path = os.path.join(self.temp_dir, blob_id)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, 'rb') as f:
            self.assertEqual(f.read(), data)

    def test_get_blob(self):
        blob_id = 'test_blob'
        data = b'Hello, World!'
        # First upload
        self.app.put('/api/blobs/' + blob_id, data=data)

        # Then get
        response = self.app.get('/api/blobs/' + blob_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_get_nonexistent_blob(self):
        blob_id = 'nonexistent'
        response = self.app.get('/api/blobs/' + blob_id)
        self.assertEqual(response.status_code, 404)
        self.assertIn('No such file', response.get_json()['error'])

    def test_delete_blob(self):
        blob_id = 'test_blob'
        data = b'Hello, World!'
        # First upload
        self.app.put('/api/blobs/' + blob_id, data=data)

        # Then delete
        response = self.app.delete('/api/blobs/' + blob_id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Deleted successfully', response.get_json()['message'])

        # Check if file is gone
        file_path = os.path.join(self.temp_dir, blob_id)
        self.assertFalse(os.path.exists(file_path))

    def test_delete_nonexistent_blob(self):
        blob_id = 'nonexistent'
        response = self.app.delete('/api/blobs/' + blob_id)
        self.assertEqual(response.status_code, 404)
        self.assertIn('No such file', response.get_json()['error'])