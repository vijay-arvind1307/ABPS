import urllib.request
import json
import time

bbox = '11.2,76.6,11.5,77.0'
query = f"""[out:json][timeout:25];
(
  way["railway"="rail"]({bbox});
  way["railway"="narrow_gauge"]({bbox});
);
out geom;
"""

req = urllib.request.Request(
    'https://overpass-api.de/api/interpreter',
    data=query.encode('utf-8'),
    headers={'User-Agent': 'IR-ABPS/1.0 (sih26027)'}
)
t0 = time.time()
try:
    res = urllib.request.urlopen(req, timeout=30)
    data = json.loads(res.read().decode('utf-8'))
    print(f'Overpass query completed in {time.time()-t0:.2f}s')
    elements = data.get('elements', [])
    print('Ways found:', len(elements))
    total_pts = sum(len(el.get('geometry', [])) for el in elements)
    print('Total geometry points:', total_pts)
    if elements:
        print('Sample way geometry sample (first 3 points):', elements[0].get('geometry', [])[:3])
except Exception as e:
    print('Error querying Overpass:', e)
