import os
import sqlite3
import logging
import pickle
import random
import smtplib
import traceback
import time
import warnings
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
import requests
from mtcnn import MTCNN
from keras_facenet import FaceNet
from flask import Flask, render_template, jsonify, request,flash,redirect,url_for

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.secret_key = "hostel_secret"
DATASET_DIR = 'dataset'
PROFILE_PIC_DIR = 'static/profile_pics'
EMBEDDINGS_DIR = 'embeddings'
VISITOR_PHOTO_DIR = 'static/visitor_photos'
embedder = FaceNet()
detector = MTCNN()
DETECTOR_TYPE = 'mtcnn'
EMBEDDINGS_CACHE = {}
threshold=0.9

os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
os.makedirs(PROFILE_PIC_DIR, exist_ok=True)
os.makedirs(VISITOR_PHOTO_DIR, exist_ok=True)

def send_pushover_alert(message, image_path=None):
    token = "YOUR_USER_KEY"
    user = "YOUR_API_TOKEN"
    data = {
        "token": token,
        "user": user,
        "message": message,
    }
    files = {}
    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            files['attachment'] = (os.path.basename(image_path), f, 'image/jpeg')
            response = requests.post("https://api.pushover.net/1/messages.json", data=data, files=files)
    else:
        response = requests.post("https://api.pushover.net/1/messages.json", data=data)
    return response.status_code == 200

def load_embeddings_cache():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, embedding FROM embeddings')
    for user_id, emb_blob in cursor.fetchall():
        EMBEDDINGS_CACHE[user_id] = pickle.loads(emb_blob) / np.linalg.norm(pickle.loads(emb_blob))
    conn.close()
    logging.debug(f"Loaded {len(EMBEDDINGS_CACHE)} embeddings into cache")

load_embeddings_cache()

def init_db():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            contact TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            profile_pic TEXT,
            dataset_folder TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_counters (
            role TEXT PRIMARY KEY,
            counter INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            embedding BLOB NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL,
            detected_speed REAL,  -- Added detected_speed column
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(user_id, date)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            photo_path TEXT NOT NULL,
            status TEXT DEFAULT 'Visitor',
            confidence REAL,
            detected_speed REAL  -- Added detected_speed column
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geo_fence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            photo_path TEXT NOT NULL,
            status TEXT DEFAULT 'Zone Breach',
            user_id TEXT
        )
    ''')

    roles = ['hostelite', 'warden', 'support_staff']
    for role in roles:
        cursor.execute('INSERT OR IGNORE INTO role_counters (role, counter) VALUES (?, 0)', (role,))
    
    # Ensure status, confidence, and detected_speed columns exist in visitors table
    cursor.execute("PRAGMA table_info(visitors)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute('ALTER TABLE visitors ADD COLUMN status TEXT DEFAULT "Visitor"')
    if 'confidence' not in columns:
        cursor.execute('ALTER TABLE visitors ADD COLUMN confidence REAL')
    if 'detected_speed' not in columns:
        cursor.execute('ALTER TABLE visitors ADD COLUMN detected_speed REAL')
    
    # Ensure confidence and detected_speed columns exist in attendance table
    cursor.execute("PRAGMA table_info(attendance)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'confidence' not in columns:
        cursor.execute('ALTER TABLE attendance ADD COLUMN confidence REAL')
    if 'detected_speed' not in columns:
        cursor.execute('ALTER TABLE attendance ADD COLUMN detected_speed REAL')
    
    conn.commit()
    conn.close()

def generate_user_id(role):
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT counter FROM role_counters WHERE role = ?', (role,))
    result = cursor.fetchone()
    counter = result[0] if result else 0
    prefix_map = {'hostelite': 'HST', 'warden': 'WRD', 'support_staff': 'STF'}
    prefix = prefix_map.get(role, 'USR')
    user_id = f"{prefix}-{counter + 1:04d}"
    conn.close()
    return user_id

init_db()

active_otps = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    if 'image' in request.files:  # Facial login
        try:
            img_file = request.files['image']
            img_data = np.frombuffer(img_file.read(), np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            faces = detector.detect_faces(img_rgb)
            if not faces:
                return jsonify({"status": "error", "message": "No face detected"})

            face = faces[0]
            x, y, w, h = face['box']
            face_img = img_rgb[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (160, 160))
            embedding = embedder.embeddings(np.expand_dims(face_img, axis=0))[0]
            embedding = embedding / np.linalg.norm(embedding)

            min_dist = float('inf')
            matched_user_id = None
            for user_id, stored_emb in EMBEDDINGS_CACHE.items():
                dist = np.linalg.norm(embedding - stored_emb)
                if dist < min_dist:
                    min_dist = dist
                    matched_user_id = user_id

            if min_dist > 1.1 or matched_user_id is None:
                return jsonify({"status": "error", "message": "Face not recognized"})

            # Verify role
            conn = sqlite3.connect('hostel.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name, role FROM users WHERE user_id = ?", (matched_user_id,))
            row = cursor.fetchone()
            conn.close()
            if not row or row[1] != 'warden':
                return jsonify({"status": "error", "message": "Only warden can login"})
            return jsonify({"status": "success", "name": row[0]})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    else:  # OTP login step 1
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")

        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        cursor.execute("SELECT email, name, role FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or row[0].lower() != email.lower() or row[2] != 'warden':
            return jsonify({"status": "error", "message": "Invalid credentials or not a warden"})

        otp = ''.join(random.choices("0123456789", k=4))  # 4-digit OTP
        active_otps[user_id] = {
            'otp': otp,
            'email': email,
            'name': row[1],
            'timestamp': time.time()
        }

        try:
            # Send OTP via email (replace credentials accordingly)
            sender = "your_email@gmail.com"
            password = "your_generated_app_password"
            subject = "HostelVision OTP Login"
            body = f"Your 4-digit OTP is: {otp}"

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, password)
                server.sendmail(sender, email, f"Subject: {subject}\n\n{body}")
        except Exception as e:
            return jsonify({"status": "error", "message": "Failed to send OTP: " + str(e)})

        return jsonify({"status": "success", "message": "OTP sent to email"})


@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    otp = data.get("otp")

    otp_data = active_otps.get(user_id)
    if not otp_data:
        return jsonify({"status": "error", "message": "No OTP found for this user"})

    if otp_data['email'].lower() != email.lower():
        return jsonify({"status": "error", "message": "Email mismatch"})

    if time.time() - otp_data['timestamp'] > 300:
        del active_otps[user_id]
        return jsonify({"status": "error", "message": "OTP expired"})

    if otp_data['otp'] != otp:
        return jsonify({"status": "error", "message": "Invalid OTP"})

    name = otp_data['name']
    del active_otps[user_id]
    return jsonify({"status": "success", "name": name})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/home')
def home():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    
    # Total Hostelites
    cursor.execute("SELECT COUNT(*) FROM users")
    total_hostelites = cursor.fetchone()[0]
    
    # Today's Attendance
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'Present'", (today,))
    today_attendance = cursor.fetchone()[0]
    
    # Unauthorized Visits
    cursor.execute("SELECT COUNT(*) FROM visitors WHERE status = 'Visitor'")
    unauthorized_visits = cursor.fetchone()[0]
    
    # Geo-Fencing Alerts
    cursor.execute("SELECT COUNT(*) FROM geo_fence WHERE status = 'Zone Breach'")
    geo_fence_alerts = cursor.fetchone()[0]
    
    # Recent Alerts
    cursor.execute('''
        SELECT timestamp, photo_path, status FROM visitors 
        WHERE status = 'Visitor' 
        UNION 
        SELECT timestamp, photo_path, status FROM geo_fence 
        WHERE status = 'Zone Breach' 
        ORDER BY timestamp DESC LIMIT 5
    ''')
    recent_alerts = [
        {
            'message': f"{row[2]} detected",
            'date': row[0].split(' ')[0],
            'time': row[0].split(' ')[1]
        }
        for row in cursor.fetchall()
    ]
    
    # Current Date & Time
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn.close()
    
    return render_template('home.html',
                         total_hostelites=total_hostelites,
                         today_attendance=today_attendance,
                         unauthorized_visits=unauthorized_visits,
                         geo_fence_alerts=geo_fence_alerts,
                         recent_alerts=recent_alerts,
                         current_datetime=current_datetime)

@app.route('/generate_user_id', methods=['POST'])
def generate_user_id_route():
    try:
        data = request.get_json()
        role = data.get('role')
        if role not in ['hostelite', 'warden', 'support_staff']:
            return jsonify({"status": "error", "message": "Invalid role"}), 400
        user_id = generate_user_id(role)
        return jsonify({"status": "success", "user_id": user_id}), 200
    except Exception as e:
        logging.error(f"Error in generate_user_id: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            user_id = request.form.get('generated_id', '').strip()
            role = request.form.get('role')
            name = request.form['name']
            age = request.form['age']
            contact = request.form['contact']
            email = request.form['email']
            photo_method = request.form['photo_method']
            if not all([user_id, role, name, age, contact, email, photo_method]):
                return jsonify({"status": "error", "message": "All fields are required"}), 400
            if not age.isdigit() or int(age) <= 0 or int(age) > 120:
                return jsonify({"status": "error", "message": "Invalid age"}), 400
            if not contact.isdigit() or len(contact) != 10:
                return jsonify({"status": "error", "message": "Contact must be 10 digits"}), 400
            if '@' not in email or '.' not in email:
                return jsonify({"status": "error", "message": "Invalid email"}), 400
            profile_pic_path = None
            if 'profile_pic' in request.files and request.files['profile_pic'].filename != '':
                profile_pic = request.files['profile_pic']
                if profile_pic.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    profile_pic_filename = f"{user_id}_{name.replace(' ', '_')}_profile{os.path.splitext(profile_pic.filename)[1]}"
                    profile_pic_path = os.path.join(PROFILE_PIC_DIR, profile_pic_filename)
                    profile_pic.save(profile_pic_path)
                    profile_pic_path = f"/{PROFILE_PIC_DIR}/{profile_pic_filename}"
            folder_name = f"{user_id}_{name.replace(' ', '_')}"
            save_path = os.path.join(DATASET_DIR, folder_name)
            os.makedirs(save_path, exist_ok=True)
            if photo_method in ['camera', 'upload']:
                if 'images' not in request.files:
                    return jsonify({"status": "error", "message": "No images uploaded"}), 400
                files = request.files.getlist('images')
                if len(files) < 20:
                    return jsonify({"status": "error", "message": "Please provide at least 20 images"}), 400
                for i, file in enumerate(files):
                    if file.filename == '':
                        continue
                    file.save(os.path.join(save_path, f"{i+1}.jpg"))
            else:
                return jsonify({"status": "error", "message": "Invalid photo method"}), 400
            conn = sqlite3.connect('hostel.db')
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (user_id, role, name, age, contact, email, profile_pic, dataset_folder)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, role, name, int(age), contact, email, profile_pic_path, save_path))
                cursor.execute('SELECT counter FROM role_counters WHERE role = ?', (role,))
                result = cursor.fetchone()
                new_counter = (result[0] + 1) if result else 1
                cursor.execute('INSERT OR REPLACE INTO role_counters (role, counter) VALUES (?, ?)', (role, new_counter))
                conn.commit()
            except sqlite3.IntegrityError as e:
                conn.close()
                if 'user_id' in str(e):
                    return jsonify({"status": "error", "message": "User ID already exists"}), 400
                elif 'email' in str(e):
                    return jsonify({"status": "error", "message": "Email already exists"}), 400
                else:
                    return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                conn.close()
            return jsonify({"status": "success", "message": "Registered Successfully!"}), 200
        except Exception as e:
            logging.error(f"Error in register: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return render_template('register.html')

@app.route('/train/<user_id>')
def train(user_id):
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, profile_pic, name, dataset_folder
        FROM users
        WHERE user_id = ?
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"status": "error", "message": "User not found"}), 404
    user = {
        'user_id': row[0],
        'profile_pic': row[1],
        'name': row[2],
        'dataset_folder': row[3]
    }
    return render_template('train.html', user=user)

@app.route('/train_model/<user_id>', methods=['POST'])
def train_model(user_id):
    try:
        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        cursor.execute('SELECT dataset_folder FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"status": "error", "message": "User not found"}), 404
        dataset_folder = row[0]
        if not os.path.exists(dataset_folder):
            conn.close()
            return jsonify({"status": "error", "message": "Dataset folder not found"}), 404
        def process_image(img_path):
            try:
                img = cv2.imread(img_path)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                faces = detector.detect_faces(img_rgb)
                if not faces or faces[0]['confidence'] < 0.9:
                    return None
                x, y, w, h = faces[0]['box']
                face_img = img_rgb[y:y+h, x:x+w]
                face_img = cv2.resize(face_img, (160, 160))
                return embedder.embeddings(np.expand_dims(face_img, axis=0))[0]
            except Exception as e:
                logging.debug(f"Error processing {img_path}: {str(e)}")
                return None
        img_paths = [os.path.join(dataset_folder, img_name) for img_name in os.listdir(dataset_folder)
                     if img_name.lower().endswith(('.jpg', '.jpeg', '.png'))]
        embeddings = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(process_image, img_paths)
            for result in results:
                if result is not None:
                    embeddings.append(result)
        if len(embeddings) < 15:
            conn.close()
            return jsonify({"status": "error", "message": f"Insufficient valid faces ({len(embeddings)}/15)"}), 400
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
        embedding_blob = pickle.dumps(avg_embedding)
        cursor.execute('INSERT INTO embeddings (user_id, embedding) VALUES (?, ?)', (user_id, embedding_blob))
        conn.commit()
        EMBEDDINGS_CACHE[user_id] = avg_embedding
        embedding_file = os.path.join(EMBEDDINGS_DIR, f'{user_id}_embedding.pkl')
        with open(embedding_file, 'wb') as f:
            pickle.dump({'embedding': avg_embedding, 'user_id': user_id}, f)
        logging.debug(f"Saved embedding to: {embedding_file}")
        conn.close()
        return jsonify({"status": "success", "message": "Training completed successfully"})
    except Exception as e:
        logging.error(f"Error in train_model: {str(e)}")
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/process_attendance', methods=['POST'])
def process_attendance():
    try:
        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        if 'image' not in request.files:
            conn.close()
            logging.error("No image provided in request")
            return jsonify({"status": "error", "message": "No image provided"}), 400
        img_file = request.files['image']
        img_data = np.frombuffer(img_file.read(), np.uint8)
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)      
        # Start timing for detection and recognition
        start_time = time.time()
        faces = detector.detect_faces(img_rgb)
        logging.debug(f"Detected {len(faces)} faces")
        if not faces:
            conn.close()
            return jsonify({"status": "error", "message": "No faces detected"}), 400
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        status_messages = []
        face_imgs = []
        face_boxes = []
        for i, face in enumerate(faces):
            if face['confidence'] < 0.9:
                logging.debug(f"Face {i+1} skipped due to low confidence: {face['confidence']}")
                status_messages.append(f"Face {i+1} skipped (low confidence)")
                continue
            x, y, w, h = face['box']
            face_img = img_rgb[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (160, 160))
            face_imgs.append(face_img)
            face_boxes.append((x, y, w, h))
        if not face_imgs:
            conn.close()
            return jsonify({"status": "error", "message": "No valid faces detected"}), 400
        face_imgs = np.array(face_imgs)
        embeddings = embedder.embeddings(face_imgs)
        # Calculate detection speed
        detection_speed = time.time() - start_time
        logging.debug(f"Detection and recognition took {detection_speed:.4f} seconds")
        debug_img = img.copy()
        attendance_records = []
        results = []
        for i, (embedding, (x, y, w, h)) in enumerate(zip(embeddings, face_boxes)):
            embedding = embedding / np.linalg.norm(embedding)
            distances = []
            for user_id, stored_emb in EMBEDDINGS_CACHE.items():
                dist = np.linalg.norm(embedding - stored_emb)
                distances.append((dist, user_id))
            distances.sort()
            min_dist, matched_user_id = distances[0] if distances else (float('inf'), None)

            # Calculate confidence score
            confidence = max(0, 100 * (1 - min_dist / threshold)) if min_dist != float('inf') else 0
            # Adjust confidence for ambiguous matches
            is_ambiguous = False
            if len(distances) > 1 and (distances[1][0] - min_dist) < 0.09:
                is_ambiguous = True
                confidence = min(confidence, 50)  # Reduce confidence for ambiguous matches
            if not matched_user_id or min_dist > threshold:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                photo_path = os.path.join(VISITOR_PHOTO_DIR, f"visitor_{timestamp}_face{i+1}.jpg")
                face_crop = img[y:y+h, x:x+w]
                cv2.imwrite(photo_path, face_crop)

                #pushover
                send_pushover_alert(
                    message=f"An unregistred person detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}!",
                    image_path=photo_path
                )

                # Insert visitor with high confidence of not being a hostelite
                visitor_confidence = 100 - confidence  # High confidence for not being a hostelite
                cursor.execute('INSERT INTO visitors (timestamp, photo_path, status, confidence, detected_speed) VALUES (?, ?, ?, ?, ?)',
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), photo_path, 'Visitor', visitor_confidence, detection_speed))
                logging.debug(f"Visitor photo saved at {photo_path} with confidence {visitor_confidence:.2f}% and detection speed {detection_speed:.4f}s")
                status_messages.append(f"Visitor detected (face {i+1}, confidence: {visitor_confidence:.2f}%, speed: {detection_speed:.4f}s)")
                results.append({
                    "face": i+1,
                    "status": "Visitor",
                    "user_id": None,
                    "confidence": round(visitor_confidence, 2),
                    "detected_speed": round(detection_speed, 4)
                })
                cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(debug_img, f"Visitor ({visitor_confidence:.2f}%, {detection_speed:.4f}s)", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            else:
                if is_ambiguous:
                    logging.warning(f"Face {i+1} ambiguous: {matched_user_id} ({min_dist}) vs {distances[1][1]} ({distances[1][0]})")
                    status_messages.append(f"Ambiguous face detected (face {i+1}, confidence: {confidence:.2f}%, speed: {detection_speed:.4f}s)")
                    results.append({
                        "face": i+1,
                        "status": "Ambiguous",
                        "user_id": matched_user_id,
                        "confidence": round(confidence, 2),
                        "detected_speed": round(detection_speed, 4)
                    })
                    cv2.rectangle(debug_img, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    cv2.putText(debug_img, f"Ambiguous ({confidence:.2f}%, {detection_speed:.4f}s)", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                    continue
                cursor.execute('SELECT id FROM attendance WHERE user_id = ? AND date = ?', (matched_user_id, today))
                if cursor.fetchone():
                    status_messages.append(f"Attendance already marked for {matched_user_id} (face {i+1}, confidence: {confidence:.2f}%, speed: {detection_speed:.4f}s)")
                    results.append({
                        "face": i+1,
                        "status": "Already Marked",
                        "user_id": matched_user_id,
                        "confidence": round(confidence, 2),
                        "detected_speed": round(detection_speed, 4)
                    })
                else:
                    attendance_records.append((matched_user_id, today, current_time, 'Present', confidence, detection_speed))
                    status_messages.append(f"Attendance marked for {matched_user_id} (face {i+1}, confidence: {confidence:.2f}%, speed: {detection_speed:.4f}s)")
                    results.append({
                        "face": i+1,
                        "status": "Present",
                        "user_id": matched_user_id,
                        "confidence": round(confidence, 2),
                        "detected_speed": round(detection_speed, 4)
                    })
                cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(debug_img, f"{matched_user_id} ({confidence:.2f}%, {detection_speed:.4f}s)", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        if attendance_records:
            cursor.executemany('INSERT INTO attendance (user_id, date, time, status, confidence, detected_speed) VALUES (?, ?, ?, ?, ?, ?)', attendance_records)
        conn.commit()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "; ".join(status_messages),
            "results": results
        })
    except Exception as e:
        logging.error(f"Error in process_attendance: {str(e)}")
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/attendance')
def attendance():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT a.user_id, u.name, a.date, a.time, a.status, a.confidence, a.detected_speed
        FROM attendance a
        JOIN users u ON a.user_id = u.user_id
        WHERE a.date = ?
        ORDER BY a.time DESC
    ''', (today,))
    present_list = [
        {'user_id': row[0], 'name': row[1], 'date': row[2], 'time': row[3], 'status': row[4], 'confidence': row[5], 'detected_speed': row[6]}
        for row in cursor.fetchall()
    ]
    cursor.execute('''
        SELECT u.user_id, u.name
        FROM users u
        LEFT JOIN attendance a ON u.user_id = a.user_id AND a.date = ?
        WHERE a.user_id IS NULL
    ''', (today,))
    absent_list = [
        {'user_id': row[0], 'name': row[1], 'date': today, 'time': '-', 'status': 'Absent', 'confidence': None, 'detected_speed': None}
        for row in cursor.fetchall()
    ]
    conn.close()
    return render_template('attendance.html', present_list=present_list, absent_list=absent_list)

@app.route('/info')
def info():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, profile_pic, name, age, contact, email, created_at, role
        FROM users
        ORDER BY CASE role
            WHEN 'warden' THEN 1
            WHEN 'support_staff' THEN 2
            WHEN 'hostelite' THEN 3
            ELSE 4
        END
    ''')
    hostelites = [
        {'user_id': row[0], 'profile_pic': row[1], 'name': row[2], 'age': row[3], 'contact': row[4], 'email': row[5], 'created_at': row[6], 'role': row[7]}
        for row in cursor.fetchall()
    ]
    conn.close()
    return render_template('info.html', hostelites=hostelites)

@app.route('/intrusion-monitor')
def intrusion_monitor():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, photo_path, status, confidence, detected_speed FROM visitors ORDER BY timestamp DESC')
    unauthorized_entries = [
        {
            'image_url': row[1],
            'date': row[0].split(' ')[0],
            'time': row[0].split(' ')[1],
            'status': row[2],
            'confidence': row[3],
            'detected_speed': row[4]
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return render_template('intrusion-monitor.html', unauthorized_entries=unauthorized_entries)
    
@app.route('/process_intrusion', methods=['POST'])
def process_intrusion():
    try:
        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        if 'image' not in request.files:
            conn.close()
            logging.error("No image provided in request")
            return jsonify({"status": "error", "message": "No image provided"}), 400
        img_file = request.files['image']
        img_data = np.frombuffer(img_file.read(), np.uint8)
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        start_time = time.time()
        faces = detector.detect_faces(img_rgb)
        logging.debug(f"Detected {len(faces)} faces")
        if not faces:
            conn.close()
            return jsonify({"status": "error", "message": "No faces detected"}), 400

        status_messages = []
        face_imgs = []
        face_boxes = []
        for i, face in enumerate(faces):
            if face['confidence'] < 0.9:
                logging.debug(f"Face {i+1} skipped due to low confidence: {face['confidence']}")
                status_messages.append(f"Face {i+1} skipped (low confidence)")
                continue
            x, y, w, h = face['box']
            face_img = img_rgb[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (160, 160))
            face_imgs.append(face_img)
            face_boxes.append((x, y, w, h))

        if not face_imgs:
            conn.close()
            return jsonify({"status": "error", "message": "No valid faces detected"}), 400

        face_imgs = np.array(face_imgs)
        embeddings = embedder.embeddings(face_imgs)
        detection_speed = time.time() - start_time
        logging.debug(f"Detection and recognition took {detection_speed:.4f} seconds")

        debug_img = img.copy()  # no rectangle or label will be drawn on this image

        for i, (embedding, (x, y, w, h)) in enumerate(zip(embeddings, face_boxes)):
            embedding = embedding / np.linalg.norm(embedding)
            distances = []
            for user_id, stored_emb in EMBEDDINGS_CACHE.items():
                dist = np.linalg.norm(embedding - stored_emb)
                distances.append((dist, user_id))
            distances.sort()
            min_dist, matched_user_id = distances[0] if distances else (float('inf'), None)
            confidence = max(0, 100 * (1 - min_dist / threshold)) if min_dist != float('inf') else 0
            if not matched_user_id or min_dist > threshold:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                photo_path = os.path.join(VISITOR_PHOTO_DIR, f"visitor_{timestamp}_face{i+1}.jpg")
                face_crop = img[y:y+h, x:x+w]
                cv2.imwrite(photo_path, face_crop)

                #pushover
                send_pushover_alert(
                    message=f"🚨 Visitor Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}!",
                    image_path=photo_path
                )

                visitor_confidence = 100 - confidence
                cursor.execute('INSERT INTO visitors (timestamp, photo_path, status, confidence, detected_speed) VALUES (?, ?, ?, ?, ?)',
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), photo_path, 'Visitor', visitor_confidence, detection_speed))
                logging.debug(f"Visitor photo saved at {photo_path} with confidence {visitor_confidence:.2f}% and detection speed {detection_speed:.4f}s")
                status_messages.append(f"Visitor detected (face {i+1}, confidence: {visitor_confidence:.2f}%, speed: {detection_speed:.4f}s)")
            else:
                if len(distances) > 1 and (distances[1][0] - min_dist) < 0.09:
                    logging.warning(f"Face {i+1} ambiguous: {matched_user_id} ({min_dist}) vs {distances[1][1]} ({distances[1][0]})")
                    status_messages.append(f"Ambiguous face detected (face {i+1}, confidence: {confidence:.2f}%, speed: {detection_speed:.4f}s)")
                else:
                    status_messages.append(f"Authorized user detected: {matched_user_id} (face {i+1}, confidence: {confidence:.2f}%, speed: {detection_speed:.4f}s)")
        conn.commit()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "; ".join(status_messages)
        })
    except Exception as e:
        logging.error(f"Error in process_intrusion: {str(e)}")
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/geo-fence-monitor')
def geo_fence_monitor():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, photo_path, status,user_id FROM geo_fence WHERE status = "Zone Breach" ORDER BY timestamp DESC')
    geo_fence_breaches = [
        {
            'image_url': row[1],
            'date': row[0].split(' ')[0],
            'time': row[0].split(' ')[1],
            'status': row[2],
            'user_id':row[3]
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return render_template('geo-fence-monitor.html', geo_fence_breaches=geo_fence_breaches)

@app.route('/save_geo_fence_boundary', methods=['POST'])
def save_geo_fence_boundary():
    try:
        data = request.get_json()
        boundary = data.get('boundary')
        if not boundary or len(boundary) < 3:
            return jsonify({"status": "error", "message": "Invalid boundary: Minimum 3 points required"}), 400
        with open(os.path.join('static', 'geo_fence_boundary.pkl'), 'wb') as f:
            pickle.dump(boundary, f)
        logging.debug(f"Saved boundary: {boundary}")
        return jsonify({"status": "success", "message": "Geo-fence boundary saved successfully"})
    except Exception as e:
        logging.error(f"Error saving geo-fence boundary: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_geo_fence_boundary')
def get_geo_fence_boundary():
    try:
        boundary_file = os.path.join('static', 'geo_fence_boundary.pkl')
        if os.path.exists(boundary_file):
            with open(boundary_file, 'rb') as f:
                boundary = pickle.load(f)
            logging.debug(f"Retrieved boundary: {boundary}")
            return jsonify({"status": "success", "boundary": boundary})
        return jsonify({"status": "success", "boundary": []})
    except Exception as e:
        logging.error(f"Error retrieving geo-fence boundary: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def is_point_in_polygon(x, y, points):
    n = len(points)
    inside = False
    j = n - 1
    for i in range(n):
        if ((points[i][1] > y) != (points[j][1] > y)) and \
           (x < (points[j][0] - points[i][0]) * (y - points[i][1]) / (points[j][1] - points[i][1]) + points[i][0]):
            inside = not inside
        j = i
    return inside

def is_box_in_polygon(x, y, w, h, polygon):
    return any(is_point_in_polygon(px, py, polygon) for px, py in [(x, y), (x+w, y), (x+w, y+h), (x, y+h)])

@app.route('/process_geo_fence', methods=['POST'])
def process_geo_fence():
    try:
        logging.debug("Starting process_geo_fence")
        if 'image' not in request.files:
            logging.error("No image provided in request")
            return jsonify({"status": "error", "message": "No image provided"}), 400

        boundary_file = os.path.join('static', 'geo_fence_boundary.pkl')
        if not os.path.exists(boundary_file):
            logging.error("Geo-fence boundary file not found")
            return jsonify({"status": "error", "message": "Geo-fence boundary not set"}), 400
        
        try:
            with open(boundary_file, 'rb') as f:
                boundary = pickle.load(f)
        except Exception as e:
            logging.error(f"Error loading boundary file: {str(e)}")
            return jsonify({"status": "error", "message": f"Error loading boundary: {str(e)}"}), 500
        
        if not boundary or len(boundary) < 3:
            logging.error(f"Invalid boundary: {boundary}")
            return jsonify({"status": "error", "message": "Invalid geo-fence boundary: Minimum 3 points required"}), 400

        img_file = request.files['image']
        img_data = np.frombuffer(img_file.read(), np.uint8)
        logging.debug("Decoding image")
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        if img is None:
            logging.error("Failed to decode image")
            return jsonify({"status": "error", "message": "Failed to decode image"}), 400
        
        logging.debug("Converting image to RGB")
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        logging.debug("Detecting faces")
        faces = detector.detect_faces(img_rgb)
        faces = [f for f in faces if f['confidence'] >= 0.9]
        logging.debug(f"Detected {len(faces)} faces with confidence >= 0.9")
        
        if not faces:
            logging.debug("No faces detected, returning early")
            return jsonify({"status": "success", "message": "No faces detected", "debug_image": None})

        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        status_messages = []
        debug_img = img.copy()
        
        # Convert boundary points to integer tuples
        try:
            boundary_points = [(int(p['x']), int(p['y'])) for p in boundary]
            logging.debug(f"Converted boundary points: {boundary_points}")
        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"Invalid boundary point format: {boundary}, error: {str(e)}")
            conn.close()
            return jsonify({"status": "error", "message": f"Invalid boundary point format: {str(e)}"}), 400

        # Draw boundary on debug image
        for j in range(len(boundary_points)):
            pt1, pt2 = boundary_points[j], boundary_points[(j+1)%len(boundary_points)]
            logging.debug(f"Drawing line from {pt1} to {pt2}")
            cv2.line(debug_img, pt1, pt2, (255,255,0), 2)

        face_imgs = []
        face_boxes = []
        for i, face in enumerate(faces):
            x, y, w, h = face['box']
            logging.debug(f"Checking face {i+1} at box ({x}, {y}, {w}, {h})")
            if not is_box_in_polygon(x, y, w, h, boundary_points):
                logging.debug(f"Face {i+1} outside boundary, skipping")
                continue
            face_img = img_rgb[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (160, 160))
            face_imgs.append(face_img)
            face_boxes.append((x, y, w, h))

        if not face_imgs:
            conn.close()
            logging.debug("No faces detected in boundary, returning early")
            return jsonify({"status": "success", "message": "No faces detected in boundary", "debug_image": None})

        logging.debug(f"Processing {len(face_imgs)} faces")
        face_imgs = np.array(face_imgs)
        embeddings = embedder.embeddings(face_imgs)

        for i, (embedding, (x, y, w, h)) in enumerate(zip(embeddings, face_boxes)):
            embedding = embedding / np.linalg.norm(embedding)
            distances = [(np.linalg.norm(embedding - emb), uid) for uid, emb in EMBEDDINGS_CACHE.items()]
            distances.sort()
            min_dist, matched_user_id = distances[0] if distances else (float('inf'), None)
            logging.debug(f"Face {i+1}: min_dist={min_dist}, matched_user_id={matched_user_id}")

            if not matched_user_id or min_dist > threshold:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                photo_path = os.path.join(VISITOR_PHOTO_DIR, f"breach_{timestamp}_face{i+1}.jpg")
                logging.debug(f"Saving unauthorized face at {photo_path}")
                cv2.imwrite(photo_path, img[y:y+h, x:x+w])

                #pushover
                send_pushover_alert(
                    message=f"An Unknown Zone Breach Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}!",
                    image_path=photo_path
                )

                cursor.execute('INSERT INTO geo_fence (timestamp, photo_path, status) VALUES (?, ?, ?)',
                               (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), photo_path, 'Zone Breach'))
                status_messages.append(f"Unauthorized breach detected (face {i+1})")
                cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(debug_img, "Unauthorized", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            else:
                cursor.execute('SELECT role FROM users WHERE user_id = ?', (matched_user_id,))
                result = cursor.fetchone()
                if result:
                    role = result[0]
                    logging.debug(f"Face {i+1}: matched role={role}")
                    if role in ['warden', 'support_staff']:
                        status_messages.append(f"Authorized {role} {matched_user_id} in zone")
                        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(debug_img, matched_user_id, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    else:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                        photo_path = os.path.join(VISITOR_PHOTO_DIR, f"breach_{timestamp}_face{i+1}.jpg")
                        logging.debug(f"Saving hostelite breach at {photo_path}")
                        cv2.imwrite(photo_path, img[y:y+h, x:x+w])

                        #pushover
                        send_pushover_alert(
                            message=f" Zone Breach Detected for {matched_user_id} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}!",
                            image_path=photo_path
                        )

                        cursor.execute('INSERT INTO geo_fence (timestamp, photo_path, status,user_id) VALUES (?, ?, ?,?)',
                                       (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), photo_path, 'Zone Breach',matched_user_id))
                        status_messages.append(f"Hostelite breach: {matched_user_id} (face {i+1})")
                        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        cv2.putText(debug_img, matched_user_id, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        conn.commit()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "; ".join(status_messages) if status_messages else "No unauthorized breaches detected",
        })

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        error_message = f"Geo-fence processing error: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500
    
@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    try:
        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        # Delete all records from both tables
        cursor.execute('DELETE FROM visitors')
        cursor.execute('DELETE FROM geo_fence')
        conn.commit()
        conn.close()
        flash('All notifications cleared successfully!', 'success')
    except Exception as e:
        logging.error(f"Error clearing notifications: {str(e)}")
        flash('Failed to clear notifications.', 'danger')
    return redirect(url_for('notifications'))


def get_db_connection():
    conn = sqlite3.connect('hostel.db')
    conn.row_factory = sqlite3.Row
    return conn

# Replace the existing insights route with this updated version
@app.route('/insights')
def insights():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch distinct dates for attendance
    cursor.execute("SELECT DISTINCT date FROM attendance ORDER BY date DESC")
    dates = [row['date'] for row in cursor.fetchall()]
    
    # Fetch hostelites (users with role 'hostelite')
    cursor.execute("SELECT user_id, name FROM users")
    hostelites = [{'user_id': row['user_id'], 'name': row['name']} for row in cursor.fetchall()]
    
    # Fetch zone breach counts per user
    cursor.execute("SELECT user_id, COUNT(*) as breach_count FROM geo_fence WHERE status = 'Zone Breach' AND user_id IS NOT NULL GROUP BY user_id")
    zone_breaches = {row['user_id']: row['breach_count'] for row in cursor.fetchall()}
    
    # Fetch 30-day attendance data
    today = datetime.now().strftime('%Y-%m-%d')
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT date, COUNT(*) as present_count 
        FROM attendance 
        WHERE status = 'Present' AND date >= ? 
        GROUP BY date 
        ORDER BY date
    """, (one_month_ago,))
    attendance_data = [{'date': row['date'], 'present_count': row['present_count']} for row in cursor.fetchall()]
    
    # Fetch monthly comparison (last two months)
    last_month_start = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT strftime('%Y-%m', date) as month, COUNT(*) as present_count 
        FROM attendance 
        WHERE status = 'Present' AND date >= ? 
        GROUP BY month 
        ORDER BY month DESC
        LIMIT 2
    """, (last_month_start,))
    monthly_comparison = [{'month': row['month'], 'present_count': row['present_count']} for row in cursor.fetchall()]
    
    # Fetch calendar data
    cursor.execute("""
        SELECT date, COUNT(*) as present_count
        FROM attendance 
        WHERE status = 'Present'
        GROUP BY date
    """)
    calendar_data = [{'date': row['date'], 'present_count': row['present_count']} for row in cursor.fetchall()]
    
    # Fetch geo-fence breaches
    cursor.execute("SELECT timestamp, photo_path, status, user_id FROM geo_fence WHERE status = 'Zone Breach' ORDER BY timestamp DESC")
    geo_fence_breaches = [
        {
            'image_url': row['photo_path'],
            'date': row['timestamp'].split(' ')[0] if ' ' in row['timestamp'] else row['timestamp'],
            'time': row['timestamp'].split(' ')[1] if ' ' in row['timestamp'] else '00:00:00',
            'status': row['status'],
            'user_id': row['user_id']
        }
        for row in cursor.fetchall()
    ]
    
    # Fetch notifications (visitors and geo-fence breaches)
    cursor.execute("SELECT timestamp, photo_path, status FROM visitors ORDER BY timestamp DESC")
    visitor_alerts = [
        {
            'type': row['status'],
            'hostelite_id': None,
            'name': None,
            'time': row['timestamp'].split(' ')[1] if ' ' in row['timestamp'] else row['timestamp'],
            'date': row['timestamp'].split(' ')[0] if ' ' in row['timestamp'] else datetime.now().strftime('%Y-%m-%d'),
            'message': f"Visitor detected",
            'photo': row['photo_path']
        }
        for row in cursor.fetchall()
    ]
    
    cursor.execute("SELECT timestamp, photo_path, status, user_id FROM geo_fence ORDER BY timestamp DESC")
    geo_fence_alerts = [
        {
            'type': row['status'],
            'hostelite_id': row['user_id'],
            'name': None,
            'time': row['timestamp'].split(' ')[1] if ' ' in row['timestamp'] else row['timestamp'],
            'date': row['timestamp'].split(' ')[0] if ' ' in row['timestamp'] else datetime.now().strftime('%Y-%m-%d'),
            'message': f"Zone breach detected",
            'photo': row['photo_path']
        }
        for row in cursor.fetchall()
    ]
    
    notifications = visitor_alerts + geo_fence_alerts
    notifications.sort(key=lambda x: x['date'] + ' ' + x['time'], reverse=True)
    
    conn.close()
    
    return render_template('insights.html', 
                         dates=dates, 
                         hostelites=hostelites, 
                         zone_breaches=zone_breaches, 
                         attendance_data=json.dumps(attendance_data),
                         monthly_comparison=json.dumps(monthly_comparison),
                         calendar_data=json.dumps(calendar_data),
                         geo_fence_breaches=geo_fence_breaches,
                         notifications=notifications)

# Replace the existing notifications route with this updated version
@app.route('/notifications')
def notifications():
    try:
        conn = sqlite3.connect('hostel.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT timestamp, photo_path, status FROM visitors ORDER BY timestamp DESC')
        visitor_alerts = [
            {
                'type': row[2],
                'hostelite_id': None,
                'name': None,
                'time': row[0].split(' ')[1] if ' ' in row[0] else row[0],
                'date': row[0].split(' ')[0] if ' ' in row[0] else datetime.now().strftime('%Y-%m-%d'),
                'message': f"Visitor detected",
                'photo': row[1]
            }
            for row in cursor.fetchall()
        ]

        cursor.execute('SELECT timestamp, photo_path, status, user_id FROM geo_fence ORDER BY timestamp DESC')
        geo_fence_alerts = [
            {
                'type': row[2],
                'hostelite_id': row[3],
                'name': None,
                'time': row[0].split(' ')[1] if ' ' in row[0] else row[0],
                'date': row[0].split(' ')[0] if ' ' in row[0] else datetime.now().strftime('%Y-%m-%d'),
                'message': f"Zone breach detected",
                'photo': row[1]
            }
            for row in cursor.fetchall()
        ]

        alerts = visitor_alerts + geo_fence_alerts
        alerts.sort(key=lambda x: x['date'] + ' ' + x['time'], reverse=True)
        
        conn.close()
        return render_template('notifications.html', alerts=alerts)
    except Exception as e:
        logging.error(f"Error in notifications: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return render_template('notifications.html', alerts=[], error=str(e))

@app.route('/individual_history/<user_id>')
def individual_history(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date, time, status, confidence 
        FROM attendance 
        WHERE user_id = ? 
        ORDER BY date DESC, time DESC
    """, (user_id,))
    
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            'date': row['date'],
            'time': row['time'],
            'status': row['status'],
            'confidence': row['confidence']
        } for row in rows
    ])

@app.route('/date_report/<date>')
def date_report(date):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get present users
    cursor.execute("""
        SELECT a.user_id, u.name, a.time, a.status 
        FROM attendance a 
        JOIN users u ON a.user_id = u.user_id 
        WHERE a.date = ? AND a.status = 'Present'
    """, (date,))
    present_list = [
        {'user_id': row['user_id'], 'name': row['name'], 'time': row['time'], 'status': row['status']}
        for row in cursor.fetchall()
    ]

    # Get absent users
    cursor.execute("""
        SELECT user_id, name FROM users
        WHERE user_id NOT IN (
            SELECT user_id FROM attendance WHERE date = ? AND status = 'Present'
        )
    """, (date,))
    absent_list = [
        {'user_id': row['user_id'], 'name': row['name'], 'time': '-', 'status': 'Absent'}
        for row in cursor.fetchall()
    ]
    conn.close()
    return jsonify({'present_list': present_list, 'absent_list': absent_list})
if __name__ == '__main__':
    app.run(debug=True)
