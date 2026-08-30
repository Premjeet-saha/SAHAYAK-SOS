# 🚨 SAHAYAK SOS: Intelligent Emergency Response Triage Engine

**SAHAYAK SOS** is a real-time emergency triage and dispatch automation platform designed for India. Built to streamline emergency response workflows, it instantly captures multi-modal distress signals (Text, Multilingual Voice/Speech, and Visual Threat Imagery), parses them using intelligent natural language processing, calculates dynamic priority scores, and dynamically routes incidents to the appropriate emergency services (Police, Fire, NDRF/SDRF, or Medical Ambulance).

---

## 🌟 Key Features

* **Multilingual Voice & Text Processing:** Fully supports English, Hindi, and Hinglish. It recognizes phonetic voice inputs (including native Devanagari script) and maps critical emergency keywords instantly.
* **Intelligent AI Triage & Scoring:** Automatically evaluates incident severity and calculates real-time priority scores (0–100) to ensure high-threat situations surface immediately at the command center.
* **Dynamic Multi-Agency Routing:** Bypasses generic responses by intelligently routing incidents to the correct emergency service:
  * 🚒 **State Fire Services** for fires, gas leaks, and explosions.
  * 🌊 **NDRF & SDRF** for flash floods, earthquakes, cloudbursts, and landslides.
  * 🚑 **National Ambulance Service** for medical trauma, cardiac arrests, and snakebites.
  * 🚓 **Police & Traffic Units** for road accidents, crime, and public safety threats.
* **Visual Threat Detection (Vision AI Simulator):** Supports direct photo uploads of disaster zones and infrastructure damage to trigger critical-tier automated routing.
* **Live GIS Mapping:** Integrates Leaflet maps with live GPS tracking to pin precise incident locations for dispatchers.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, Flask-CORS
* **Frontend:** HTML5, CSS3, JavaScript, Leaflet.js
* **Speech Recognition:** Web Speech API (Multilingual support for `hi-IN` and `en-US`)

---

## 🚀 Getting Started Locally

Follow these steps to set up and run the project on your local machine.

### 1. Clone the Repository
```bash
git clone [https://github.com/Premjeet-saha/SAHAYAK-SOS.git](https://github.com/Premjeet-saha/SAHAYAK-SOS.git)
cd SAHAYAK-SOS
