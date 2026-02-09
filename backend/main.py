from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["bot_tracking"]
collection = db["sessions"]

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

@app.post("/collect")
def collect_data(data: SessionData):
    record = {
        "session_id": data.session_id,
        "events": [e.dict() for e in data.events],
        "created_at": datetime.datetime.utcnow()
    }
    collection.insert_one(record)
    return {"status": "success", "events_received": len(data.events)}
