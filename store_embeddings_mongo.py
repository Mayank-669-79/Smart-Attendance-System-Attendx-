import os
import cv2
import numpy as np
import face_recognition
from pymongo import MongoClient

# ---------------------------
# MongoDB Setup
# ---------------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["face_attendance"]
collection = db["students"]

# ---------------------------
# Dataset Path
# ---------------------------
dataset_path = "dataset"

# ---------------------------
# Process Dataset
# ---------------------------
for person_name in os.listdir(dataset_path):

    person_folder = os.path.join(dataset_path, person_name)

    if not os.path.isdir(person_folder):
        continue

    print(f"Processing {person_name}...")

    embeddings = []

    for image_name in os.listdir(person_folder):
        image_path = os.path.join(person_folder, image_name)

        img = cv2.imread(image_path)
        if img is None:
            continue

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        faces = face_recognition.face_encodings(rgb)

        if len(faces) > 0:
            embeddings.append(faces[0])

    if len(embeddings) == 0:
        print(f"No face found for {person_name}")
        continue

    # ✅ Average embedding
    avg_embedding = np.mean(embeddings, axis=0)

    # ---------------------------
    # Save to MongoDB
    # ---------------------------
    collection.update_one(
        {"name": person_name},
        {
            "$set": {
                "name": person_name,
                "embedding": avg_embedding.tolist()
            }
        },
        upsert=True
    )

    print(f"Saved {person_name} to DB")

print("✅ All embeddings stored in MongoDB")