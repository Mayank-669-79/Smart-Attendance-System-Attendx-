from pymongo import MongoClient
from collections import defaultdict

client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]

sessions = list(db["sessions"].find())

# =========================
# GROUP DATA
# =========================
attendance = defaultdict(lambda: defaultdict(float))
class_duration_map = defaultdict(float)

# Step 1: Calculate class durations
for s in sessions:
    class_id = s["class_id"]
    duration = (s["end"] - s["start"]).seconds / 60

    if duration > class_duration_map[class_id]:
        class_duration_map[class_id] = duration

# Step 2: Sum student durations per subject
for s in sessions:
    name = s["name"]
    subject = s.get("subject", "Unknown")
    class_id = s["class_id"]

    duration = (s["end"] - s["start"]).seconds / 60

    attendance[name][subject] += duration

# =========================
# CALCULATE PERCENTAGE
# =========================
summary = []

for name in attendance:
    for subject in attendance[name]:

        total_time = attendance[name][subject]

        # total class duration = sum of all class sessions of that subject
        total_class_time = sum(class_duration_map.values())

        percent = (total_time / total_class_time) * 100 if total_class_time > 0 else 0

        # Status rules
        if percent < 20:
            status = "Absent"
        elif percent < 50:
            status = "Half"
        else:
            status = "Full"

        summary.append({
            "name": name,
            "subject": subject,
            "attendance_percent": round(percent, 2),
            "attention_percent": round(percent, 2),  # placeholder
            "status": status
        })

# =========================
# SAVE TO DB
# =========================
summary_col = db["attendance_summary"]

for s in summary:
    summary_col.update_one(
        {"name": s["name"], "subject": s["subject"]},
        {"$set": s},
        upsert=True
    )

print("✅ Subject-wise Attendance Calculated & Saved")