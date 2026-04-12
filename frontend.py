import streamlit as st
import pandas as pd
from pymongo import MongoClient
import subprocess

st.set_page_config(page_title="AttendX", layout="wide")

# =============================
# MONGODB CONNECTION
# =============================
client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]

summary_col = db["attendance_summary"]
sessions_col = db["sessions"]
queries_col = db["queries"]
logs_col = db["edit_logs"]   # 🔥 NEW

# =============================
# LOAD DATA
# =============================
def load_summary():
    return pd.DataFrame(list(summary_col.find({}, {"_id": 0})))

def load_sessions():
    return pd.DataFrame(list(sessions_col.find({}, {"_id": 0})))

def load_queries():
    return pd.DataFrame(list(queries_col.find({}, {"_id": 0})))

def load_logs():
    return pd.DataFrame(list(logs_col.find({}, {"_id": 0})))

summary_df = load_summary()
sessions_df = load_sessions()
queries_df = load_queries()
logs_df = load_logs()

# =============================
# SIDEBAR
# =============================
st.sidebar.title("AttendX")
role = st.sidebar.selectbox("View as", ["Admin", "Teacher", "Student"])

st.title(f"{role} Dashboard")

# =============================
# EMPTY DATA WARNING
# =============================
if summary_df.empty:
    st.warning("⚠️ No attendance data yet. Run a class first.")

# =============================
# ADMIN DASHBOARD
# =============================
if role == "Admin":

    if not summary_df.empty:
        total_students = summary_df["name"].nunique()

        full = len(summary_df[summary_df["status"] == "Full"])
        half = len(summary_df[summary_df["status"] == "Half"])
        absent = len(summary_df[summary_df["status"] == "Absent"])

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Students", total_students)
        col2.metric("Full Attendance", full)
        col3.metric("Half Attendance", half)
        col4.metric("Absent", absent)

        st.divider()
        st.subheader("Attendance Summary")
        st.dataframe(summary_df, use_container_width=True)

    # =============================
    # 🔥 ADMIN EDIT CONTROL
    # =============================
    st.divider()
    st.subheader("🛠 Admin Attendance Control")

    if not summary_df.empty:

        student_name = st.selectbox("Select Student", summary_df["name"].unique())

        student_data = summary_df[summary_df["name"] == student_name]

        subject = st.selectbox("Select Subject", student_data["subject"])

        current = student_data[student_data["subject"] == subject].iloc[0]

        st.write(f"Current Attendance: {current['attendance_percent']}%")

        new_percent = st.slider(
            "Update Attendance %",
            0, 100,
            int(current["attendance_percent"])
        )

        reason = st.text_input("Reason for change")

        if new_percent < 20:
            status = "Absent"
        elif new_percent < 50:
            status = "Half"
        else:
            status = "Full"

        if st.button("Update Attendance"):

            # UPDATE MAIN DATA
            summary_col.update_one(
                {"name": student_name, "subject": subject},
                {
                    "$set": {
                        "attendance_percent": new_percent,
                        "attention_percent": new_percent,
                        "status": status
                    }
                }
            )

            # 🔥 SAVE LOG
            logs_col.insert_one({
                "name": student_name,
                "subject": subject,
                "old_attendance": current["attendance_percent"],
                "new_attendance": new_percent,
                "edited_by": "admin",
                "reason": reason if reason else "Manual update",
                "timestamp": str(pd.Timestamp.now())
            })

            st.success("✅ Attendance Updated + Logged")

    # =============================
    # 🔥 QUERY MANAGEMENT
    # =============================
    st.divider()
    st.subheader("📩 Student Queries")

    if not queries_df.empty:
        st.dataframe(queries_df, use_container_width=True)

        if "status" in queries_df.columns:
            pending = queries_df[queries_df["status"] == "Pending"]

            if not pending.empty:
                selected = st.selectbox(
                    "Select Query to Resolve",
                    pending.index,
                    format_func=lambda i: f"{pending.loc[i,'name']} - {pending.loc[i,'subject']}"
                )

                if st.button("Mark as Resolved"):
                    q = pending.loc[selected]

                    queries_col.update_one(
                        {
                            "name": q["name"],
                            "subject": q["subject"],
                            "timestamp": q["timestamp"]
                        },
                        {"$set": {"status": "Resolved"}}
                    )

                    st.success("✅ Query Resolved")
            else:
                st.info("No pending queries")
    else:
        st.info("No queries yet")

    # =============================
    # 🔥 EDIT LOGS DISPLAY
    # =============================
    st.divider()
    st.subheader("📜 Edit Logs")

    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.info("No edits yet")

# =============================
# TEACHER DASHBOARD
# =============================
elif role == "Teacher":

    st.subheader("Start Class Setup")

    subject = st.selectbox("Select Subject", [
        "CSET203", "CSET207", "CSET209", "CSET210", "CSET228", "CSET244"
    ])

    duration = st.slider("Class Duration (minutes)", 30, 120, 60)

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button("Start Class"):
        subprocess.Popen([
            "python", "mark_attendance.py", subject, str(duration)
        ])
        st.success(f"📷 Class Started for {subject}")

    if col2.button("End Class & Process Attendance"):
        subprocess.run(["python", "calculate_duration.py"])
        st.success("✅ Attendance Calculated!")

    st.divider()

    st.subheader("Session Logs")
    st.dataframe(sessions_df, use_container_width=True)

    if not summary_df.empty:
        st.subheader("Subject-wise Summary")
        st.dataframe(summary_df, use_container_width=True)

# =============================
# STUDENT DASHBOARD
# =============================
else:

    st.subheader("Student Login")

    student_input = st.text_input("Enter Your Name")

    if st.button("Login"):
        if student_input:
            st.session_state["student"] = student_input

    if "student" in st.session_state:

        student_name = st.session_state["student"]
        st.success(f"Welcome {student_name}")

        student_df = summary_df[summary_df["name"] == student_name]

        if student_df.empty:
            st.warning("No record found")
        else:
            # ATTENDANCE
            st.subheader("Subject-wise Attendance")
            st.dataframe(student_df, use_container_width=True)

            st.bar_chart(
                student_df.set_index("subject")["attendance_percent"]
            )

            st.divider()

            overall = student_df["attendance_percent"].mean()
            st.metric("Overall Attendance", f"{round(overall,2)}%")
            st.progress(overall / 100)

            # SESSIONS
            st.divider()
            st.subheader("Your Sessions")

            if not sessions_df.empty and "name" in sessions_df.columns:
                student_sessions = sessions_df[sessions_df["name"] == student_name]
                st.dataframe(student_sessions, use_container_width=True)

            # =============================
            # QUERY SYSTEM
            # =============================
            st.divider()
            st.subheader("Raise Attendance Query")

            query_subject = st.selectbox(
                "Select Subject",
                student_df["subject"].unique()
            )

            query_text = st.text_area("Describe your issue")

            if st.button("Submit Query"):
                if query_text.strip() != "":
                    queries_col.insert_one({
                        "name": student_name,
                        "subject": query_subject,
                        "message": query_text,
                        "status": "Pending",
                        "timestamp": str(pd.Timestamp.now())
                    })
                    st.success("✅ Query Submitted")
                else:
                    st.warning("Please enter your issue")

            # VIEW OWN QUERIES
            st.subheader("Your Queries")

            if not queries_df.empty and "name" in queries_df.columns:
                student_queries = queries_df[queries_df["name"] == student_name]

                if not student_queries.empty:
                    st.dataframe(student_queries, use_container_width=True)
                else:
                    st.info("No queries raised yet")
            else:
                st.info("No queries yet")