"""
Migration script to remap authentic block sections to canonical C40 and clean up legacy corridors.
Remaps:
- SEC_MDU_TDN, SEC_TDN_TMQ, SEC_TMQ_VPT, SEC_VPT_SRT, SEC_SRT_CVP, SEC_CVP_KDU, SEC_KDU_MEJ, SEC_MEJ_TEN -> C40 (ID: 30)
- SEC_MEJ_TN -> C41 (ID: 56)
- SEC_MAS_MS -> C01, SEC_SA_ED -> C21, SEC_MS_CGL -> C07, SEC_VM_TPJ -> C28
- Purges mock sections SECTION-103, SECTION-204 from C40
- Purges empty legacy corridor records (62-71)
"""
import sys
sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.models.models import Corridor, RailwaySection

def migrate():
    db = SessionLocal()
    try:
        c40 = db.query(Corridor).filter(Corridor.prototype_code == 'C40').first()
        if not c40:
            print("ERROR: Corridor C40 not found!")
            return
        
        c41 = db.query(Corridor).filter(Corridor.prototype_code == 'C41').first()
        c01 = db.query(Corridor).filter(Corridor.prototype_code == 'C01').first()
        c07 = db.query(Corridor).filter(Corridor.prototype_code == 'C07').first()
        c21 = db.query(Corridor).filter(Corridor.prototype_code == 'C21').first()
        c28 = db.query(Corridor).filter(Corridor.prototype_code == 'C28').first()

        # 1. Remap C40 sections
        c40_section_ids = [
            'SEC_MDU_TDN', 'SEC_TDN_TMQ', 'SEC_TMQ_VPT', 'SEC_VPT_SRT',
            'SEC_SRT_CVP', 'SEC_CVP_KDU', 'SEC_KDU_MEJ', 'SEC_MEJ_TEN'
        ]
        for sec_id in c40_section_ids:
            sec = db.query(RailwaySection).filter(RailwaySection.section_id == sec_id).first()
            if sec:
                sec.corridor_id = c40.id
                print(f"Remapped {sec.section_id} to C40 (ID: {c40.id})")

        # 2. Remap SEC_MEJ_TN to C41
        if c41:
            mej_tn = db.query(RailwaySection).filter(RailwaySection.section_id == 'SEC_MEJ_TN').first()
            if mej_tn:
                mej_tn.corridor_id = c41.id
                print(f"Remapped SEC_MEJ_TN to C41 (ID: {c41.id})")

        # 3. Remap corridor 63 sections
        remaps_63 = [
            ('SEC_MAS_MS', c01.id if c01 else None),
            ('SEC_SA_ED', c21.id if c21 else None),
            ('SEC_MS_CGL', c07.id if c07 else None),
            ('SEC_VM_TPJ', c28.id if c28 else None)
        ]
        for sec_id, target_corr_id in remaps_63:
            if target_corr_id:
                s = db.query(RailwaySection).filter(RailwaySection.section_id == sec_id).first()
                if s:
                    s.corridor_id = target_corr_id
                    print(f"Remapped {sec_id} to corridor ID {target_corr_id}")

        # 4. Remove mock sections SECTION-103 and SECTION-204
        mock_secs = db.query(RailwaySection).filter(
            RailwaySection.section_id.in_(['SECTION-103', 'SECTION-204'])
        ).all()
        for ms in mock_secs:
            print(f"Deleting mock section {ms.section_id} (ID: {ms.id})")
            db.delete(ms)

        db.commit()

        # 5. Delete empty legacy corridors (prototype_code is None)
        legacy_corrs = db.query(Corridor).filter(Corridor.prototype_code == None).all()
        for lc in legacy_corrs:
            sec_count = db.query(RailwaySection).filter(RailwaySection.corridor_id == lc.id).count()
            if sec_count == 0:
                print(f"Deleting empty legacy corridor {lc.id} ({lc.name})")
                db.delete(lc)
            else:
                print(f"Legacy corridor {lc.id} ({lc.name}) still has {sec_count} sections, keeping")

        db.commit()
        print("Migration committed successfully.")

        # Verification
        c40_now = db.query(RailwaySection).filter(RailwaySection.corridor_id == c40.id).all()
        print(f"\nC40 now has {len(c40_now)} sections:")
        for s in c40_now:
            fc = s.from_station.code if s.from_station else '?'
            tc = s.to_station.code if s.to_station else '?'
            print(f"  {s.id}: {s.section_id} ({fc} -> {tc}) {s.name}")

    except Exception as ex:
        db.rollback()
        print(f"Migration error: {ex}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    migrate()
