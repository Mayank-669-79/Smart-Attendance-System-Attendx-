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
CLASS_DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 60  # minutes

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
    names = []
    embeddings = []

    for doc in students_col.find():
        names.append(doc["name"])
        embeddings.append(np.array(doc["embedding"]))

    return names, embeddings

known_names, known_embeddings = load_embeddings()
print("Loaded students:", known_names)

# =========================
# SESSION TRACKING
# =========================
active_sessions = {}
GRACE_PERIOD = 120  # seconds

def update_session(name):
    now = datetime.now()

    if name not in active_sessions:
        active_sessions[name] = {
            "start": now,
            "last_seen": now
        }
    else:
        active_sessions[name]["last_seen"] = now

def check_exits():
    now = datetime.now()

    for name in list(active_sessions.keys()):
        last_seen = active_sessions[name]["last_seen"]

        if (now - last_seen).seconds > GRACE_PERIOD:
            session = active_sessions.pop(name)
            save_session(name, session["start"], last_seen)

def save_session(name, start, end):
    sessions_col.insert_one({
        "name": name,
        "subject": CLASS_SUBJECT,
        "class_id": CLASS_ID,
        "start": start,
        "end": end
    })
    print(f"✅ Saved session for {name}")

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

    # 🔥 AUTO STOP WHEN CLASS ENDS
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

        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        # Ignore far faces
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

        print(f"Match: {best_name} | Distance: {round(best_distance,2)}")

        # =========================
        # SESSION UPDATE
        # =========================
        if best_name != "Unknown":
            update_session(best_name)

        # =========================
        # DRAW
        # =========================
        text = f"{best_name} ({round(best_distance,2)})"
        color = (0, 255, 0) if best_name != "Unknown" else (0, 0, 255)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, text, (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    check_exits()

    cv2.imshow("Smart Attendance System", frame)

    if cv2.waitKey(1) == 27:
        break

# =========================
# SAVE REMAINING SESSIONS
# =========================
for name in active_sessions:
    session = active_sessions[name]
    save_session(name, session["start"], session["last_seen"])

cap.release()
cv2.destroyAllWindows()

print("✅ Class session completed")