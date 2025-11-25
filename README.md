# 📌 HostelVision-AI: An Intelligent Hostel Surveillance System

HostelVision-AI is a **real-time facial recognition surveillance system** designed for hostels to automate **attendance, visitor monitoring, geo-fence violation alerts, and security notifications**.  
Using **MTCNN for face detection** and **FaceNet 512-D embeddings for recognition**, the system provides fast, accurate, and contactless identification.

---

## 🚀 Key Features
- 👨‍🎓 Automatic attendance using face recognition
- 🕵️ Unknown visitor detection and image capture
- 🔔 Push notifications through Pushover API
- 🔐 Email-based OTP authentication for the warden
- 📍 Geo-fence violation alert system
- 📊 Live analytics dashboard
- ⚡ High-performance embedding-based matching (FaceNet)

---

## 🛠 Tech Stack

| Component | Technology |
|----------|-------------|
| Backend | Flask (Python) |
| Database | SQLite (`hostel.db`) |
| Face Detection | MTCNN |
| Face Recognition | FaceNet Embeddings |
| Frontend | HTML, CSS, JavaScript |
| Notifications | Email + Pushover API |

---

## 📂 Project Structure

HostelVision-AI/
│ app.py → Main backend application
│ hostel.db → SQLite database
│ requirements.txt → Dependencies
│ README.md → Documentation
├─ dataset/ → Training images (each folder = one student)
├─ embeddings/ → Stored embedding (.pkl) files
├─ static/
│ ├─ media/ → Temporary snapshots
│ ├─ profile_pic/ → Student profile photos
│ ├─ visitor_photos/ → Unknown visitor images
│ ├─ geo_fence_boundary.pkl → Geo-fence trained model
│ ├─ css / js → UI resources
├─ templates/ → HTML pages
└─ venv/ → Virtual environment (local)

---

## 🖥 System Requirements
- Python **3.8 – 3.11**
- Webcam / CCTV camera
- Minimum **8 GB RAM recommended**
- Internet connection (for OTP + notifications)

---

## 📌 Installation & Setup

### 1️⃣ Create Virtual Environment (optional)
```sh
python -m venv venv

Windows:
venv\Scripts\activate

Linux/Mac:
source venv/bin/activate

### 2️⃣ Install Dependencies
pip install -r requirements.txt

### 3️⃣ Run the Application
python app.py

Open the dashboard in browser:
http://127.0.0.1:5000

## 🔧 Manual Configuration (Important)
#### ✔ Pushover Alert Setup

Inside app.py:
PUSHOVER_USER_KEY = "YOUR_USER_KEY"
PUSHOVER_API_TOKEN = "YOUR_API_TOKEN"
Keys available at: https://pushover.net

#### ✔ Email OTP Setup

Inside app.py:
sender = "your_email@gmail.com"
password = "your_generated_app_password"
⚠ Gmail users must generate a Google App Password (not normal password).

## 🧠 System Workflow

Admin registers a student with multiple face images

FaceNet generates embeddings and stores them

During monitoring:

MTCNN detects face

FaceNet compares embeddings

If match → attendance is recorded

If unknown → visitor image stored + Pushover alert sent

If restricted area violation → geo-fence alert triggered

## 🔮 Future Enhancements

Face anti-spoofing (prevent image attack)

Multi-camera monitoring

Cloud database + mobile app integration

Voice alert announcements inside hostel corridors

## 👨‍💻 Developer

Name: Manjunatha H B
Project: HostelVision-AI – An Intelligent Hostel Surveillance System
Domain: AI • Computer Vision • Web Technologies

## 📜 License

This project is intended for academic and research purposes only.
