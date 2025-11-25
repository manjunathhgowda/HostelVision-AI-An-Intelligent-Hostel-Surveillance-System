📌 HostelVision-AI: An Intelligent Hostel Surveillance System

HostelVision-AI is a real-time facial recognition and smart surveillance system designed to automate attendance, visitor monitoring, and security alerts inside hostel premises.
Using MTCNN for face detection and FaceNet embeddings for recognition, the system enables accurate, fast, and contactless student authentication.

🚀 Key Features

👨‍🎓 Automatic attendance using face recognition

🕵️ Visitor / unknown face alerts with captured images

🔔 Push notification alerts via Pushover API

🔐 OTP-based warden authentication via email

📍 Geo-fence violation alert system

📊 Live analytics dashboard

⚡ High performance embedding-based matching (FaceNet)

🛠 Tech Stack
Component	        Technology
Backend	            Flask (Python)
Database	        SQLite (hostel.db)
Face Detection	    MTCNN
Face Recognition	FaceNet embeddings
Frontend	        HTML, CSS, JavaScript
Notification	    Email + Pushover API

📂 Project Folder Structure
HostelVision-AI/
│ app.py                 → Main backend application
│ hostel.db              → SQLite database
│ requirements.txt       → Dependencies
│ README.md              → Documentation
├─ dataset/              → Training images (each user folder)
├─ embeddings/           → Generated .pkl embedding files
├─ static/
│   ├─ media/            → Temporary video snapshots
│   ├─ profile_pic/      → Student profile photos
│   ├─ visitor_photos/   → Unknown visitor log images
│   ├─ geo_fence_boundary.pkl → Restricted area trained model
│   ├─ css , js          → UI resources
│
├─ templates/            → All HTML pages
└─ venv/                 → Virtual environment (local)

🖥 System Requirements

Python 3.8 – 3.11
Webcam / CCTV camera
Minimum 8GB RAM recommended
Internet connection (for OTP + notifications)

📌 Installation & Setup
1️⃣ Create Virtual Environment (optional)
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate   # Linux/Mac

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Run the Application
python app.py


Open in browser:

http://127.0.0.1:5000

🔧 Required Manual Configurations (Important)
✔ Pushover Alert Setup (for visitor & geo-fence notifications)

Inside app.py, update:

PUSHOVER_USER_KEY = "YOUR_USER_KEY"
PUSHOVER_API_TOKEN = "YOUR_API_TOKEN"


Get keys from: https://pushover.net

✔ Email OTP Setup (for secure login)

Inside app.py, update:

sender = "your_email@gmail.com"
password = "your_generated_app_password"


⚠ Gmail users must create an App Password (not normal password) via Google account security.

🧠 How the System Works
1️⃣ Admin registers a student with multiple face images
2️⃣ FaceNet embeddings are generated and stored
3️⃣ During monitoring:
       ▪ MTCNN detects face
       ▪ FaceNet compares embeddings
4️⃣ If match → mark attendance
5️⃣ If unknown → store visitor image + send alert via Pushover
6️⃣ If restricted area violation → geo-fence alert triggered

🔮 Future Enhancement Ideas
Face anti-spoofing (photo attack detection)
Multi-camera monitoring
Cloud database & mobile app extension
Voice alert system inside hostel corridors

👨‍💻 Developer
Name : Manjunatha H B
Project : HostelVision-AI: An Intelligent Hostel Surveillance System
Domain : AI + Computer Vision + Web Technologies

📜 License
This project is intended for academic and research purposes only.