import sqlite3
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from rapidfuzz import process, fuzz

DB_PATH = os.path.join("data", "sanctions.db")

ENTITIES_CACHE = []
NAMES_ONLY_CACHE = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ENTITIES_CACHE, NAMES_ONLY_CACHE
    if not os.path.exists(DB_PATH):
        raise RuntimeError("Database file not found! Run 'python etl.py' first.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ofac_id, full_name, search_name, entity_type, program FROM sanctioned_entities")
    rows = cursor.fetchall()
    conn.close()
    
    ENTITIES_CACHE = [
        {
            "ofac_id": r[0],
            "full_name": r[1],
            "search_name": r[2],
            "entity_type": r[3],
            "program": r[4]
        }
        for r in rows
    ]
    NAMES_ONLY_CACHE = [e["search_name"] for e in ENTITIES_CACHE]
    print(f"🚀 API Ready! Warm cache populated with {len(ENTITIES_CACHE)} entities.")
    yield
    ENTITIES_CACHE.clear()

app = FastAPI(
    title="OpenRisk Compliance API",
    description="High-performance, free Sanctions & PEP screening API",
    version="1.0.0",
    lifespan=lifespan
)

class MatchResult(BaseModel):
    ofac_id: int
    matched_name: str
    confidence_score: float = Field(..., description="Match score from 0.0 to 100.0")
    entity_type: str
    sanctions_program: str

class ScreeningResponse(BaseModel):
    query_name: str
    is_flagged: bool
    total_matches: int
    matches: list[MatchResult]

@app.get("/v1/screen", response_model=ScreeningResponse)
def screen_entity(
    name: str = Query(..., min_length=2, description="Name of person or company to screen"),
    threshold: float = Query(75.0, ge=50.0, le=100.0, description="Minimum fuzzy match confidence score")
):
    clean_query = name.strip().lower()
    
    results = process.extract(
        clean_query, 
        NAMES_ONLY_CACHE, 
        scorer=fuzz.token_sort_ratio, 
        limit=5
    )
    
    matches = []
    for match_str, score, index in results:
        if score >= threshold:
            entity = ENTITIES_CACHE[index]
            matches.append(MatchResult(
                ofac_id=entity["ofac_id"],
                matched_name=entity["full_name"],
                confidence_score=round(score, 2),
                entity_type=entity["entity_type"],
                sanctions_program=entity["program"]
            ))
            
    return ScreeningResponse(
        query_name=name,
        is_flagged=len(matches) > 0,
        total_matches=len(matches),
        matches=matches
    )
