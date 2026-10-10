import os
import sqlite3
import pandas as pd

OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
DB_PATH = os.path.join("data", "sanctions.db")

def fetch_and_build_db():
    print("📥 Downloading live OFAC SDN list...")
    headers = [
        "ent_num", "SDN_Name", "SDN_Type", "Program", 
        "Title", "Call_Sign", "Vess_type", "Tonnage", 
        "GRT", "Vess_flag", "Vess_owner", "Remarks"
    ]
    
    df = pd.read_csv(OFAC_SDN_URL, header=None, names=headers, on_bad_lines='skip')
    
    df = df.dropna(subset=['SDN_Name'])
    df['SDN_Name'] = df['SDN_Name'].astype(str).str.strip()
    df['SDN_Type'] = df['SDN_Type'].fillna('Individual').astype(str).str.strip()
    df['Program'] = df['Program'].fillna('UNKNOWN').astype(str).str.strip()
    
    df['search_name'] = df['SDN_Name'].str.lower()

    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sanctioned_entities (
            ofac_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            search_name TEXT NOT NULL,
            entity_type TEXT,
            program TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("💾 Writing records to SQLite database...")
    entities = [
        (row['ent_num'], row['SDN_Name'], row['search_name'], row['SDN_Type'], row['Program'])
        for _, row in df.iterrows()
    ]
    
    cursor.executemany("""
        INSERT OR REPLACE INTO sanctioned_entities 
        (ofac_id, full_name, search_name, entity_type, program)
        VALUES (?, ?, ?, ?, ?)
    """, entities)
    
    conn.commit()
    conn.close()
    print(f"✅ Success! Loaded {len(entities)} entities into {DB_PATH}.")

if __name__ == "__main__":
    fetch_and_build_db()
