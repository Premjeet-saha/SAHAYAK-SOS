# 🚨 RescueMap: Intelligent Crisis Navigation System

> **Team SignalZero** | Google Solution Challenge 2026  
> **Team Leader:** Premjeet Saha

---

## 📌 Problem Statement

During disasters and emergencies, victims and rescue teams operate on disconnected, outdated information. There is no real-time bridge between a person in crisis and the responders trying to reach them — leading to delayed rescues, missed signals, and preventable loss of life.

---

## 💡 What is RescueMap?

RescueMap is a real-time crisis navigation platform that bridges the gap between emergency victims and rescue teams. When someone sends an SOS — even a panicked, unstructured text message — RescueMap uses **Google Gemini AI** to parse it, extract the location, and instantly plot it on a live **Google Maps dashboard** for rescue teams.

---

## ⚙️ How It Works

```
Victim sends SOS (SMS / web)
        ↓
Google Gemini AI parses message → extracts lat/lon + emergency type
        ↓
Flask backend receives POST /report-emergency → stores data
        ↓
Rescue dashboard polls GET /get-victim every few seconds
        ↓
Google Maps renders live marker + trajectory Polyline
        ↓
Rescue team navigates to exact victim location in real time
```

---

## 🔥 Features

- **AI-Powered SOS Parsing** — Gemini reads unstructured panic messages and extracts GPS coordinates automatically
- **Live Rescue Map Dashboard** — Google Maps with animated bounce markers, InfoWindows, and neon Polyline trajectory paths
- **Real-Time Data Sync** — Frontend polls backend via Fetch API, no page refresh needed
- **Emergency Reporting API** — RESTful `/report-emergency` endpoint accepts SOS from any device
- **Dark Mode Command Center UI** — Status overlay with live victim count, badges, and timestamps
- **Cloud Deployment** — Flask server on Google Cloud Run, always-on and auto-scaling
- **Simulation Tools** — `send_sos.py` and `track_person.py` to demo victim tracking

---

## 🗂️ Project Structure

```
RescueMap/
├── brain.py            # Flask backend — API routes, Gemini integration
├── index.html          # Rescue team dashboard — Google Maps UI
├── send_sos.py         # Simulates a victim sending an SOS signal
├── track_person.py     # Simulates live victim movement/tracking
├── requirements.txt    # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Google Maps JavaScript API key
- Google Gemini API key

### Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/RescueMap.git
cd RescueMap

# Install dependencies
pip install -r requirements.txt

# Set your API keys
export GEMINI_API_KEY="your_gemini_api_key"
export MAPS_API_KEY="your_maps_api_key"

# Run the backend
python brain.py
```

### Simulate an Emergency

```bash
# In a new terminal — send a victim SOS
python send_sos.py

# Track victim movement in real time
python track_person.py
```

Then open `index.html` in your browser to see the live rescue dashboard.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript (ES6+) |
| Mapping | Google Maps JavaScript API |
| Backend | Python 3, Flask, Flask-CORS |
| AI | Google Gemini API |
| Cloud | Google Cloud Platform — Cloud Run |
| Data | JSON, Python requests library |

---

## ☁️ Cloud Deployment

The Flask backend is containerized and deployed on **Google Cloud Run** for continuous, scalable availability — critical during mass disaster events.

---

## 🔮 Future Roadmap

- [ ] Native Android/iOS mobile app with one-tap SOS
- [ ] Google Firestore for persistent emergency logs
- [ ] Google Routes API for intelligent rescue team routing
- [ ] Predictive AI — pre-deploy teams based on weather + risk data

---

## 👥 Team SignalZero

Built with 🔴 urgency and 💙 purpose for the **Google Solution Challenge 2026**.

> *"Zero signal. Maximum response."*
