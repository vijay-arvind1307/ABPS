import urllib.request
import json

endpoints = [
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass-api.de/api/interpreter'
]
query = '[out:json][timeout:15];way["railway"="narrow_gauge"](11.3,76.7,11.4,76.9);out geom;'
for ep in endpoints:
    try:
        req = urllib.request.Request(ep, data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=15) as res:
            d = json.loads(res.read().decode('utf-8'))
            els = d.get('elements', [])
            total_pts = sum(len(e.get('geometry', [])) for e in els)
            print(ep, 'SUCCESS! Elements:', len(els), 'Total coords:', total_pts)
            if total_pts > 0:
                break
    except Exception as e:
        print(ep, 'Error:', e)
