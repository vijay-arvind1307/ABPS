import sqlite3
import os
import sys

def migrate_database(db_path: str = "backend/abps.db"):
    if not os.path.exists(db_path):
        print(f"[MIGRATE] Database {db_path} does not exist yet. It will be created on startup.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"[MIGRATE] Running schema migrations on {db_path}...")

    # 1. Update departments table
    cursor.execute("PRAGMA table_info(departments)")
    dept_cols = [row[1] for row in cursor.fetchall()]
    if "discipline" not in dept_cols:
        cursor.execute("ALTER TABLE departments ADD COLUMN discipline VARCHAR(100)")
        print("  Added discipline to departments")
    if "asset_domain" not in dept_cols:
        cursor.execute("ALTER TABLE departments ADD COLUMN asset_domain VARCHAR(50)")
        print("  Added asset_domain to departments")
    if "is_active" not in dept_cols:
        cursor.execute("ALTER TABLE departments ADD COLUMN is_active BOOLEAN DEFAULT 1")
        print("  Added is_active to departments")

    # 2. Update maintenance_jobs table
    cursor.execute("PRAGMA table_info(maintenance_jobs)")
    job_cols = [row[1] for row in cursor.fetchall()]

    new_job_cols = {
        "start_station_code": "VARCHAR(10)",
        "start_station_name": "VARCHAR(100)",
        "end_station_code": "VARCHAR(10)",
        "end_station_name": "VARCHAR(100)",
        "user_priority": "VARCHAR(10) DEFAULT 'MEDIUM'",
        "calculated_criticality": "FLOAT DEFAULT 50.0",
        "calculated_safety_impact": "FLOAT DEFAULT 50.0",
        "calculated_urgency": "FLOAT DEFAULT 50.0",
        "criticality_label": "VARCHAR(20) DEFAULT 'MEDIUM'",
        "safety_impact_label": "VARCHAR(20) DEFAULT 'MEDIUM'",
        "urgency_label": "VARCHAR(20) DEFAULT 'MEDIUM'",
        "priority_explanation": "JSON",
        "planner_override_score": "FLOAT",
        "planner_override_reason": "TEXT",
        "planner_override_by_id": "INTEGER",
        "planner_override_at": "DATETIME",
        "planner_remarks": "TEXT",
        "department_remarks": "TEXT",
        "state_history_json": "JSON",
        "execution_status": "VARCHAR(30) DEFAULT 'NOT_STARTED'",
        "actual_start_min": "INTEGER",
        "actual_end_min": "INTEGER",
        "completion_pct": "FLOAT DEFAULT 0.0",
        "delay_minutes": "INTEGER DEFAULT 0",
        "variance_minutes": "INTEGER DEFAULT 0"
    }

    for col_name, col_type in new_job_cols.items():
        if col_name not in job_cols:
            cursor.execute(f"ALTER TABLE maintenance_jobs ADD COLUMN {col_name} {col_type}")
            print(f"  Added {col_name} to maintenance_jobs")

    # 3. Update execution_records table
    cursor.execute("PRAGMA table_info(execution_records)")
    exec_cols = [row[1] for row in cursor.fetchall()]
    new_exec_cols = {
        "job_id": "INTEGER",
        "planned_start_min": "INTEGER",
        "planned_end_min": "INTEGER",
        "actual_start_min": "INTEGER",
        "actual_end_min": "INTEGER",
        "variance_min": "INTEGER DEFAULT 0",
        "completion_pct": "FLOAT DEFAULT 0.0",
        "responsible_department": "VARCHAR(50)",
        "remarks": "TEXT"
    }
    for col_name, col_type in new_exec_cols.items():
        if col_name not in exec_cols:
            cursor.execute(f"ALTER TABLE execution_records ADD COLUMN {col_name} {col_type}")
            print(f"  Added {col_name} to execution_records")

    # 4. Create notifications table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            department_id INTEGER,
            title VARCHAR(150) NOT NULL,
            message TEXT NOT NULL,
            notification_type VARCHAR(50) DEFAULT 'INFO',
            target_entity VARCHAR(50),
            target_id VARCHAR(50),
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(department_id) REFERENCES departments(id)
        )
    """)
    print("  Created notifications table if not exists")

    # 5. Clean all fake/test maintenance jobs, block demands, and plans
    cursor.execute("DELETE FROM execution_records")
    cursor.execute("DELETE FROM plan_jobs")
    cursor.execute("DELETE FROM plan_versions")
    cursor.execute("DELETE FROM what_if_scenarios")
    cursor.execute("DELETE FROM block_plans")
    cursor.execute("DELETE FROM block_demands")
    cursor.execute("DELETE FROM maintenance_job_resources")
    cursor.execute("DELETE FROM maintenance_dependencies")
    cursor.execute("DELETE FROM maintenance_jobs")
    cursor.execute("DELETE FROM block_windows")
    cursor.execute("DELETE FROM train_section_occupancies")
    cursor.execute("DELETE FROM train_movements")
    cursor.execute("DELETE FROM train_route_stops")
    cursor.execute("DELETE FROM trains")
    print("  Cleaned fake maintenance jobs, plans, windows, and mock trains (0 records active)")

    conn.commit()
    conn.close()
    print("[MIGRATE] Schema migration completed successfully.")

if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "backend/abps.db"
    migrate_database(db_file)
