from flask import Flask
import requests

app = Flask(__name__)

@app.route('/')
def index():
    try:
        # 'BACKEND_URL' is the service name used in the Docker network
        os.getenv("BACKEND_URL")
        response = requests.get("http://backend:5000/api/data")
        data = response.json()
        return f"<h1>Backend says: {data['message']}</h1>"
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
