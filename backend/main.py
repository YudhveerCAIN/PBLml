from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
import datetime
import joblib
import pandas as pd
import os
import time

from feature_extractor import extract_session_features

app = FastAPI()

# -------------------------
# CORS Configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MongoDB Connection
# -------------------------
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URL)

db = client["bot_tracking"]

sessions_collection = db["sessions"]
predictions_collection = db["predictions"]

# -------------------------
# Load trained model
# -------------------------
model = joblib.load("model.pkl")

print("✅ Model loaded successfully")

# -------------------------
# Session buffers for real-time detection
# -------------------------
session_buffers = {}

WINDOW_SIZE = 5  # seconds

# -------------------------
# Request Models
# -------------------------
class Event(BaseModel):
    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    scrollY: Optional[int] = None
    keyDelay: Optional[int] = None
    timestamp: int


class SessionData(BaseModel):
    site_id: str
    session_id: str
    events: List[Event]


# -------------------------
# Root endpoint
# -------------------------
@app.get("/")
def home():
    return {"message": "Bot Detection API Running"}


# -------------------------
# Collect + Real-Time Predict
# -------------------------
@app.post("/collect")
def collect_data(data: SessionData):

    try:

        # -------------------------
        # Store raw events
        # -------------------------
        record = {
            "site_id": data.site_id,
            "session_id": data.session_id,
            "events": [e.dict() for e in data.events],
            "created_at": datetime.datetime.utcnow()
        }

        sessions_collection.insert_one(record)

        # -------------------------
        # Update real-time buffer
        # -------------------------
        if data.session_id not in session_buffers:
            session_buffers[data.session_id] = []

        session_buffers[data.session_id].extend([e.dict() for e in data.events])

        # -------------------------
        # Sliding window filter
        # -------------------------
        now = int(time.time() * 1000)

        session_buffers[data.session_id] = [
            e for e in session_buffers[data.session_id]
            if now - e["timestamp"] < WINDOW_SIZE * 1000
        ]

        # -------------------------
        # Extract features
        # -------------------------
        features = extract_session_features(data.session_id)

        if not features:
            return {
                "status": "collecting",
                "events_received": len(data.events),
                "message": "Not enough data yet"
            }

        # -------------------------
        # Prepare dataframe
        # -------------------------
        df = pd.DataFrame([features])

        df = df[model.feature_names_in_]

        # -------------------------
        # Model prediction
        # -------------------------
        probability = model.predict_proba(df)[0][1]

        threshold = 0.75

        prediction = 1 if probability >= threshold else 0

        # -------------------------
        # Store prediction
        # -------------------------
        predictions_collection.update_one(
            {"session_id": data.session_id},
            {
                "$set": {
                    "site_id": data.site_id,
                    "prediction": int(prediction),
                    "bot_probability": float(probability),
                    "updated_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )

        # -------------------------
        # Return result
        # -------------------------
        return {
            "status": "analyzed",
            "site_id": data.site_id,
            "session_id": data.session_id,
            "prediction": "BOT" if prediction == 1 else "HUMAN",
            "bot_probability": float(probability)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }