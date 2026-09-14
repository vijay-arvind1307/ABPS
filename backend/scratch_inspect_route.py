import json
import math

with open('c:/ABPS/backend/datameet_sr_corridors.json', 'r') as f:
    corr = json.load(f)

def haversine(c1, c2):
    R = 6371.0
    dlat = math.radians(c2[1] - c1[1])
    dlon = math.radians(c2[0] - c1[0])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(c1[1]))*math.cos(math.radians(c2[1]))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

ms_ten_pts = corr['MS_TEN']['coordinates']
print(f"MS_TEN has {len(ms_ten_pts)} coordinates.")
total_dist = 0.0
for i in range(len(ms_ten_pts) - 1):
    total_dist += haversine(ms_ten_pts[i], ms_ten_pts[i+1])
print(f"Total track distance MS -> TEN: {total_dist:.2f} km")

mas_cbe_pts = corr['MAS_CBE']['coordinates']
print(f"MAS_CBE has {len(mas_cbe_pts)} coordinates.")
total_cbe = 0.0
for i in range(len(mas_cbe_pts) - 1):
    total_cbe += haversine(mas_cbe_pts[i], mas_cbe_pts[i+1])
print(f"Total track distance MAS -> CBE: {total_cbe:.2f} km")
