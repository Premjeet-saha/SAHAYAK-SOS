import requests
import time

# A path from KIIT Square towards Big Bazaar
path = [
    {"lat": 20.3506, "lng": 85.8135, "msg": "Victim moving... near KIIT"},
    {"lat": 20.3480, "lng": 85.8150, "msg": "Victim moving... passing DLF Cyber City"},
    {"lat": 20.3450, "lng": 85.8180, "msg": "Victim moving... near Patia Station Road"},
    {"lat": 20.3400, "lng": 85.8210, "msg": "Victim reached safe zone: Magnetic Square"}
]

print("🚀 Starting Real-Time Tracking...")

for step in path:
    requests.post("http://127.0.0.1:5000/report-emergency", json={
        "lat": step["lat"],
        "lng": step["lng"],
        "status": step["msg"]
    })
    print(f"Sent: {step['msg']}")
    time.sleep(4) # Wait 4 seconds between movements

print("✅ Navigation Sequence Complete.")