from pymongo import MongoClient
from collections import defaultdict

# =========================
# DB CONNECTION
# =========================
client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]

sessions_col = db["sessions"]
summary_col = db["attendance_summary"]

sessions = list(sessions_col.find())

# =========================
# DATA STRUCTURES
# =========================
attendance = defaultdict(lambda: defaultdict(float))

# 🔥 ATTENTION STRUCTURE
attention_data = defaultdict(
    lambda: defaultdict(lambda: {"attentive": 0, "total": 0})
)

subject_total_time = defaultdict(float)

# =========================
# STEP 1: TOTAL CLASS TIME PER SUBJECT
# =========================
for s in sessions:
    subject = s.get("subject")

    if not subject or subject == "Unknown":
        continue

    if not s.get("start") or not s.get("end"):
        continue

    duration = (s["end"] - s["start"]).total_seconds() / 60
    subject_total_time[subject] += duration

# =========================
# STEP 2: STUDENT TIME + ATTENTION
# =========================
for s in sessions:
    name = s.get("name")
    subject = s.get("subject")

    if not name or not subject or subject == "Unknown":
        continue

    if not s.get("start") or not s.get("end"):
        continue

    # Attendance time
    duration = (s["end"] - s["start"]).total_seconds() / 60
    attendance[name][subject] += duration

    # 🔥 Attention Data (SAFE HANDLING)
    attentive = s.get("attentive_frames") or 0
    total = s.get("total_frames") or 0

    attention_data[name][subject]["attentive"] += attentive
    attention_data[name][subject]["total"] += total

# =========================
# STEP 3: FINAL CALCULATION
# =========================
summary = []

for name in attendance:
    for subject in attendance[name]:

        student_time = attendance[name][subject]
        total_time = subject_total_time[subject]

        # 🎯 ATTENDANCE %
        if total_time > 0:
            attendance_percent = (student_time / total_time) * 100
        else:
            attendance_percent = 0

        # 🔥 ATTENTION %
        attentive = attention_data[name][subject]["attentive"]
        total = attention_data[name][subject]["total"]

        if total > 0:
            attention_percent = (attentive / total) * 100
        else:
            attention_percent = 0

        # 🔒 CLAMP TO 100
        attention_percent = min(attention_percent, 100)

        # =========================
        # STATUS RULES
        # =========================
        if attendance_percent < 20:
            status = "Absent"
        elif attendance_percent < 50:
            status = "Half"
        else:
            status = "Full"

        summary.append({
            "name": name,
            "subject": subject,
            "attendance_percent": round(attendance_percent, 2),
            "attention_percent": round(attention_percent, 2),
            "status": status
        })

# =========================
# SAVE TO DATABASE
# =========================
summary_col.delete_many({})  # clear old data

if summary:
    summary_col.insert_many(summary)

print("✅ Attendance + Attention Calculated Successfully")