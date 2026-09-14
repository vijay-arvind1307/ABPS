import sqlite3
import os

DB_PATHS = [
    os.path.join(os.path.dirname(__file__), "abps.db"),
    os.path.join(os.path.dirname(__file__), "..", "abps.db")
]

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"[MIGRATION] DB file {db_path} does not exist, skipping.")
        return

    print(f"[MIGRATION] Applying coordination schema to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Create coordinated_block_plans table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coordinated_block_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_code VARCHAR(40) UNIQUE NOT NULL,
        corridor_id INTEGER REFERENCES corridors(id),
        corridor_name VARCHAR(150),
        section_id INTEGER REFERENCES railway_sections(id),
        section_name VARCHAR(150),
        plan_date DATETIME,
        start_min INTEGER NOT NULL,
        end_min INTEGER NOT NULL,
        duration_min INTEGER NOT NULL,
        status VARCHAR(30) DEFAULT 'PROPOSED',
        strategy VARCHAR(30) DEFAULT 'PLAN_A',
        objective_score FLOAT DEFAULT 96.0,
        conflicts_count INTEGER DEFAULT 0,
        blocks_saved INTEGER DEFAULT 0,
        possession_time_saved_min INTEGER DEFAULT 0,
        is_parallel BOOLEAN DEFAULT 1,
        departments_json JSON,
        work_breakdown_json JSON,
        alternatives_json JSON,
        reasoning_json JSON,
        planner_reason TEXT,
        rejection_reason TEXT,
        modification_reason TEXT,
        created_by_id INTEGER REFERENCES users(id),
        approved_by_id INTEGER REFERENCES users(id),
        created_at DATETIME,
        approved_at DATETIME
    )
    """)

    # 2. Add coordinated_plan_id and coordination_status to maintenance_jobs if not existing
    cursor.execute("PRAGMA table_info(maintenance_jobs)")
    job_cols = [row[1] for row in cursor.fetchall()]

    if "coordinated_plan_id" not in job_cols:
        print("  -> Adding coordinated_plan_id to maintenance_jobs...")
        cursor.execute("ALTER TABLE maintenance_jobs ADD COLUMN coordinated_plan_id INTEGER REFERENCES coordinated_block_plans(id)")

    if "coordination_status" not in job_cols:
        print("  -> Adding coordination_status to maintenance_jobs...")
        cursor.execute("ALTER TABLE maintenance_jobs ADD COLUMN coordination_status VARCHAR(30) DEFAULT 'NOT_CHECKED'")

    conn.commit()
    conn.close()
    print(f"[MIGRATION] Successfully updated {db_path}.")

def main():
    for p in DB_PATHS:
        migrate_db(os.path.abspath(p))

if __name__ == "__main__":
    main()
