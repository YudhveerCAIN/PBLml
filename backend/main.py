from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
import datetime
import joblib
import pandas as pd
import os

from feature_extractor import extract_session_features

app = FastAPI()

# -------------------------
# CORS Configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",  # local testing
        "http://localhost:5500",
        "*"  # allow deployed frontend (Netlify/Vercel)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MongoDB Connection
# -------------------------
# Uses environment variable for deployment
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URL)

db = client["bot_tracking"]

sessions_collection = db["sessions"]
predictions_collection = db["predictions"]

# -------------------------
# Load trained model once
# -------------------------
model = joblib.load("model.pkl")

print("✅ Model loaded successfully")

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
    session_id: str
    events: List[Event]


# -------------------------
# Root endpoint
# -------------------------
@app.get("/")
def home():
    return {"message": "Bot Detection API Running"}


# -------------------------
# Collect + Auto Predict
# -------------------------
@app.post("/collect")
def collect_data(data: SessionData):

    try:

        # -------------------------
        # Store events
        # -------------------------
        record = {
            "session_id": data.session_id,
            "events": [e.dict() for e in data.events],
            "created_at": datetime.datetime.utcnow()
        }

        sessions_collection.insert_one(record)

        # -------------------------
        # Extract session features
        # -------------------------
        features = extract_session_features(data.session_id)

        if not features:
            return {
                "status": "collecting",
                "events_received": len(data.events),
                "message": "Not enough data yet"
            }

        # -------------------------
        # Convert to DataFrame
        # -------------------------
        df = pd.DataFrame([features])

        # Align with model training order
        df = df[model.feature_names_in_]

        # -------------------------
        # Model prediction
        # -------------------------
        prediction = model.predict(df)[0]
        probability = model.predict_proba(df)[0][1]

        # -------------------------
        # Store prediction
        # -------------------------
        predictions_collection.update_one(
            {"session_id": data.session_id},
            {
                "$set": {
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
            "session_id": data.session_id,
            "prediction": "BOT" if prediction == 1 else "HUMAN",
            "bot_probability": float(probability)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }