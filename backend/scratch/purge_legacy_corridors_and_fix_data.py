"""
Remediation script for IR-ABPS Database:
1. Adds `version` column to `coordinated_block_plans` if not present.
2. Remaps sections from legacy unnumbered corridors (1, 2, 3, 4, 10, 11, 12, 13, 14, 15) to canonical C01-C46 corridors.
3. Purges legacy corridor rows, leaving strictly C01 through C46.
4. Repairs corrupted `trains.source_code = 'RAILRADAR'` by setting to genuine origin station code.
"""

import sqlite3
import os
import sys

def migrate_db(db_path: str):
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return

    print(f"\n[MIGRATION] Applying remediation on {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Add version column to coordinated_block_plans if missing
    cur.execute("PRAGMA table_info(coordinated_block_plans)")
    cols = [r[1] for r in cur.fetchall()]
    if "version" not in cols:
        cur.execute("ALTER TABLE coordinated_block_plans ADD COLUMN version INTEGER DEFAULT 1 NOT NULL")
        print("  Added 'version' column to coordinated_block_plans.")
    else:
        print("  'version' column already exists in coordinated_block_plans.")

    # 2. Remap legacy corridor sections to canonical corridors
    # Canonical Corridor IDs in DB:
    # C01 (16): MAS -> AJJ
    # C02 (17): AJJ -> JTJ
    # C07 (22): CGL -> VM
    # C18 (33): ED -> TPJ
    # C21 (25): ED -> PTJ
    # C28 (44): TPJ -> DG
    # C31 (47): TJ -> KIK
    # C40 (30): MDU -> TEN
    # C41 (56): MEJ -> TN
    # C42 (57): TEN -> TSI
    # C43 (58): TSI -> SCT
    # C46 (61): NCJ -> CAPE

    # Remap C40 sections from corridor 10 -> corridor 30
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 30
        WHERE corridor_id = 10 AND section_id IN (
            'SEC_MDU_TDN', 'SEC_TDN_TMQ', 'SEC_TMQ_VPT', 'SEC_VPT_SRT',
            'SEC_SRT_CVP', 'SEC_CVP_KDU', 'SEC_KDU_MEJ', 'SEC_MEJ_TEN'
        )
    """)
    # Remap C41 section from corridor 10 -> corridor 56
    cur.execute("UPDATE railway_sections SET corridor_id = 56 WHERE section_id = 'SEC_MEJ_TN'")

    # Remap C01 & C02 sections from corridor 2
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 17
        WHERE corridor_id = 2 AND section_id IN ('SEC_JTJ_VN', 'SEC_VN_AB', 'SEC_AB_KPD', 'SEC_KPD_AJJ')
    """)
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 16
        WHERE corridor_id = 2 AND section_id IN ('SEC_AJJ_TRL', 'SEC_TRL_AVD', 'SEC_AVD_MAS')
    """)

    # Remap C21 & C18 sections from corridor 11
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 25
        WHERE corridor_id = 11 AND section_id IN ('SEC_CBE_IGU', 'SEC_IGU_TUP', 'SEC_TUP_UKL', 'SEC_UKL_ED')
    """)
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 33
        WHERE corridor_id = 11 AND section_id IN ('SEC_ED_SGE', 'SEC_SGE_SA')
    """)

    # Remap C46 sections from corridor 12
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 61
        WHERE corridor_id = 12 AND section_id IN ('SEC_TEN_VLY', 'SEC_VLY_NCJ')
    """)

    # Remap C42 & C43 sections from corridor 13
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 58
        WHERE corridor_id = 13 AND section_id IN ('SEC_VPT_SVKS', 'SEC_SVKS_RJPM', 'SEC_RJPM_SNKL', 'SEC_SNKL_TSI')
    """)
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 57
        WHERE corridor_id = 13 AND section_id IN ('SEC_TSI_ASD', 'SEC_ASD_TEN')
    """)

    # Remap C31 section from corridor 14
    cur.execute("UPDATE railway_sections SET corridor_id = 47 WHERE section_id = 'SEC_MV_NGT'")

    # Remap sections from corridor 1
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 22
        WHERE corridor_id = 1 AND section_id IN ('SEC_MAS_MS', 'SEC_MS_TBM', 'SEC_TBM_CGL', 'SEC_MS_CGL')
    """)
    cur.execute("""
        UPDATE railway_sections
        SET corridor_id = 44
        WHERE corridor_id = 1 AND section_id IN ('SEC_VM_VRI', 'SEC_VRI_ALU', 'SEC_ALU_LLI', 'SEC_LLI_SRGM', 'SEC_SRGM_TPJ', 'SEC_VM_TPJ')
    """)
    cur.execute("UPDATE railway_sections SET corridor_id = 33 WHERE corridor_id = 1 AND section_id = 'SEC_SA_ED'")

    # Delete Delhi fixture sections (corridor 4)
    cur.execute("DELETE FROM railway_sections WHERE corridor_id = 4")

    # Check remaining sections with legacy corridor
    cur.execute("SELECT count(*) FROM railway_sections WHERE corridor_id < 16")
    rem_secs = cur.fetchone()[0]
    print(f"  Sections remaining on legacy corridors: {rem_secs}")

    # Remap any maintenance jobs or coordinated plans referencing legacy corridors
    cur.execute("UPDATE maintenance_jobs SET corridor_id = 30 WHERE corridor_id = 10")
    cur.execute("UPDATE maintenance_jobs SET corridor_id = 22 WHERE corridor_id = 1")
    cur.execute("UPDATE maintenance_jobs SET corridor_id = 25 WHERE corridor_id = 11")
    cur.execute("UPDATE coordinated_block_plans SET corridor_id = 30 WHERE corridor_id = 10")
    cur.execute("UPDATE coordinated_block_plans SET corridor_id = 22 WHERE corridor_id = 1")
    # block_plans does not have corridor_id, no update needed

    # 3. Purge the 10 legacy corridor rows
    cur.execute("DELETE FROM corridors WHERE id IN (1, 2, 3, 4, 10, 11, 12, 13, 14, 15)")
    print("  Purged legacy corridor records (1, 2, 3, 4, 10, 11, 12, 13, 14, 15).")

    cur.execute("SELECT count(*), min(prototype_code), max(prototype_code) FROM corridors")
    total_corr, min_c, max_c = cur.fetchone()
    print(f"  Total operational corridors in DB: {total_corr} ({min_c} to {max_c})")

    # 4. Repair corrupted trains.source_code = 'RAILRADAR'
    cur.execute("""
        SELECT t.train_number, s.station_code
        FROM trains t
        JOIN train_route_stops s ON s.train_number = t.train_number AND s.sequence = 1
        WHERE t.source_code = 'RAILRADAR'
    """)
    fixed_count = 0
    for t_num, stn_code in cur.fetchall():
        if stn_code and stn_code != 'RAILRADAR':
            cur.execute("UPDATE trains SET source_code = ? WHERE train_number = ?", (stn_code, t_num))
            fixed_count += 1

    # Any remaining trains with source_code = 'RAILRADAR', find min sequence stop
    cur.execute("""
        UPDATE trains
        SET source_code = (
            SELECT station_code FROM train_route_stops
            WHERE train_number = trains.train_number
            ORDER BY sequence ASC LIMIT 1
        )
        WHERE source_code = 'RAILRADAR' AND EXISTS (
            SELECT 1 FROM train_route_stops WHERE train_number = trains.train_number
        )
    """)
    conn.commit()
    print(f"  Repaired {fixed_count} corrupted train origin station codes.")

    # Check if any RAILRADAR source codes remain
    cur.execute("SELECT count(*) FROM trains WHERE source_code = 'RAILRADAR'")
    bad_count = cur.fetchone()[0]
    print(f"  Remaining trains with source_code = 'RAILRADAR': {bad_count}")

    conn.close()
    print("[MIGRATION] Complete.")

if __name__ == "__main__":
    for path in ["c:/ABPS/backend/abps.db", "c:/ABPS/abps.db"]:
        migrate_db(path)
