import requests

# This simulates an incoming SMS being processed by your "Brain"
url = "http://127.0.0.1:5000/report-emergency"
sos_msg = {
    "lat": 20.252, 
    "lng": 85.833, 
    "status": "URGENT: Flood Victim at State Museum"
}

try:
    response = requests.post(url, json=sos_msg)
    print("📡 SOS Signal Sent!")
    print(f"Server Response: {response.json()}")
except Exception as e:
    print(f"❌ Connection Failed: Is brain.py running? \nError: {e}")