from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Starting position: KIIT University area
victim_data = {
    "lat": 20.3506, 
    "lng": 85.8135,
    "status": "System Online: Waiting for SOS..."
}

@app.route('/get-victim', methods=['GET'])
def send_data():
    return jsonify(victim_data)

@app.route('/report-emergency', methods=['POST'])
def receive_data():
    global victim_data
    data = request.get_json()
    if data:
        # We force these to be floats (numbers) so the Map doesn't crash
        victim_data = {
            "lat": float(data['lat']),
            "lng": float(data['lng']),
            "status": str(data['status'])
        }
        print(f"🚀 SOS RECEIVED: {victim_data['status']}")
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    # use_reloader=False prevents OneDrive sync issues from crashing the server
    app.run(debug=True, port=5000, use_reloader=False)