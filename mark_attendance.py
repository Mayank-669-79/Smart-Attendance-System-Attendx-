import cv2
import numpy as np
import face_recognition
from pymongo import MongoClient
from datetime import datetime, timedelta
import sys

# =========================
# INPUT FROM FRONTEND
# =========================
CLASS_SUBJECT = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
CLASS_DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 60

CLASS_ID = datetime.now().strftime("%Y%m%d_%H%M")
CLASS_START_TIME = datetime.now()
CLASS_END_TIME = CLASS_START_TIME + timedelta(minutes=CLASS_DURATION)

print(f"📘 Subject: {CLASS_SUBJECT}")
print(f"⏱ Duration: {CLASS_DURATION} minutes")

# =========================
# DB SETUP
# =========================
client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]

students_col = db["students"]
sessions_col = db["sessions"]

# =========================
# LOAD EMBEDDINGS
# =========================
def load_embeddings():
    names, embeddings = [], []

    for doc in students_col.find():
        names.append(doc["name"])
        embeddings.append(np.array(doc["embedding"]))

    return names, embeddings

known_names, known_embeddings = load_embeddings()
print("Loaded students:", known_names)

# =========================
# TRACKING STRUCTURES
# =========================
active_sessions = {}
attention_sessions = {}

GRACE_PERIOD = 120  # seconds

# =========================
# 🔥 IMPROVED ATTENTION DETECTOR
# =========================
def is_attentive(face_location):
    top, right, bottom, left = face_location

    width = right - left
    height = bottom - top

    if height == 0:
        return False

    ratio = width / height

    # 🔥 Realistic attention conditions
    if ratio < 0.6 or ratio > 1.6:
        return False

    # Too small face → far away → not attentive
    if height < 90:
        return False

    return True

# =========================
# UPDATE SESSION
# =========================
def update_session(name, attentive):
    now = datetime.now()

    if name not in active_sessions:
        active_sessions[name] = {
            "start": now,
            "last_seen": now
        }

        attention_sessions[name] = {
            "attentive_frames": 0,
            "total_frames": 0
        }
    else:
        active_sessions[name]["last_seen"] = now

    # 🔥 FRAME TRACKING
    attention_sessions[name]["total_frames"] += 1

    if attentive:
        attention_sessions[name]["attentive_frames"] += 1

# =========================
# SAVE SESSION
# =========================
def save_session(name, start, end):

    attention = attention_sessions.get(name, {
        "attentive_frames": 0,
        "total_frames": 0
    })

    sessions_col.insert_one({
        "name": name,
        "subject": CLASS_SUBJECT,
        "class_id": CLASS_ID,
        "start": start,
        "end": end,
        "attentive_frames": attention["attentive_frames"],
        "total_frames": attention["total_frames"]
    })

    print(f"✅ Saved session for {name}")

    # 🔥 IMPORTANT: RESET after saving
    if name in attention_sessions:
        del attention_sessions[name]

# =========================
# CHECK EXIT
# =========================
def check_exits():
    now = datetime.now()

    for name in list(active_sessions.keys()):
        last_seen = active_sessions[name]["last_seen"]

        if (now - last_seen).seconds > GRACE_PERIOD:
            session = active_sessions.pop(name)
            save_session(name, session["start"], last_seen)

# =========================
# CAMERA START
# =========================
cap = cv2.VideoCapture(0)
THRESHOLD = 0.43

print("🚀 Smart Attendance Running...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # AUTO STOP
    if datetime.now() >= CLASS_END_TIME:
        print("⏰ Class time ended automatically")
        break

    # =========================
    # PERFORMANCE BOOST
    # =========================
    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small)
    face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

        # Scale back
        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        if (bottom - top) < 80:
            continue

        best_name = "Unknown"
        best_distance = 999

        # =========================
        # MATCHING
        # =========================
        for i in range(len(known_embeddings)):
            distance = np.linalg.norm(face_encoding - known_embeddings[i])

            if distance < best_distance:
                best_distance = distance
                best_name = known_names[i]

        if best_distance > THRESHOLD:
            best_name = "Unknown"

        # =========================
        # ATTENTION CHECK
        # =========================
        attentive = is_attentive((top, right, bottom, left))

        # =========================
        # UPDATE SESSION
        # =========================
        if best_name != "Unknown":
            update_session(best_name, attentive)

        # =========================
        # DRAW
        # =========================
        if attentive:
            label = f"{best_name} (Focused)"
        else:
            label = f"{best_name} (Not Focused)"

        color = (0, 255, 0) if best_name != "Unknown" else (0, 0, 255)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, label, (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # CHECK EXIT STUDENTS
    check_exits()

    cv2.imshow("Smart Attendance System", frame)

    if cv2.waitKey(1) == 27:
        break

# =========================
# SAVE REMAINING
# =========================
for name in active_sessions:
    session = active_sessions[name]
    save_session(name, session["start"], session["last_seen"])

cap.release()
cv2.destroyAllWindows()

print("✅ Class session completed")