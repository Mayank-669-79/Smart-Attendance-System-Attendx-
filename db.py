from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]

students_collection = db["students"]