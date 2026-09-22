import urllib.request
import json
import time
import os

OUTPUT_FILE = "c:/ABPS/backend/osm_tn_branches.json"

# Bounding boxes for branch lines:
BRANCH_BBOXES = {
    "NMR_MTP_UAM": (11.25, 76.65, 11.45, 77.00),     # Nilgiri Mountain Railway
    "MDU_TENI_BDNK": (9.85, 77.30, 10.10, 78.15),    # Theni - Bodinayakkanur
    "DELTA_TJ_KIK": (10.60, 79.10, 11.00, 80.00),     # Thanjavur - Karaikal & Velankanni
    "TTP_AGX_DELTA": (10.25, 79.55, 10.65, 80.00),    # Tiruturaipundi - Agastiyampalli
    "TEN_TCN": (8.45, 77.65, 8.80, 78.20),            # Tirunelveli - Tiruchendur
    "TEN_TSI_SCT": (8.70, 77.20, 9.05, 77.75),        # Tirunelveli - Tenkasi - Sengottai
    "CUPJ_VRI": (11.45, 79.30, 11.80, 79.80),         # Cuddalore - Vriddhachalam
    "VRI_SA": (11.45, 78.10, 11.75, 79.40),           # Vriddhachalam - Salem
    "CGL_AJJ": (12.65, 79.60, 13.15, 80.05),          # Chengalpattu - Arakkonam
    "VM_KPD": (11.90, 79.00, 13.05, 79.55),           # Villupuram - Katpadi
}

endpoint = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"

results = {}
if os.path.exists(OUTPUT_FILE):
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception:
        results = {}

for name, (s, w, n, e) in BRANCH_BBOXES.items():
    if name in results and len(results[name]) > 0:
        print(f"Skipping {name}, already cached ({len(results[name])} ways)")
        continue

    print(f"Fetching {name} ({s},{w},{n},{e})...")
    query = f"""[out:json][timeout:25];
(
  way["railway"~"rail|narrow_gauge"]({s},{w},{n},{e});
);
out geom;
"""
    try:
        req = urllib.request.Request(endpoint, data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode('utf-8'))
            elements = data.get('elements', [])
            print(f"  Got {len(elements)} ways for {name}")
            results[name] = elements
            time.sleep(0.5)
    except Exception as err:
        print(f"  Error fetching {name}: {err}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f)

print(f"\nSaved {len(results)} branch geometries to {OUTPUT_FILE}!")
