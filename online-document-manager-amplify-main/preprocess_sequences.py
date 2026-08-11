#!/usr/bin/env python3
"""
preprocess_sequences.py
Reads per-user JSONL from S3, encodes features, builds sliding windows,
saves X.npy and encoders.pkl locally and uploads to S3 processed prefix.
"""

import boto3, json, pickle, math
import numpy as np
from datetime import datetime

# ---------- CONFIG ----------
AWS_REGION = "ap-south-1"
S3_BUCKET = "secure-ml-pushkar-2025"                # your bucket
RAW_PREFIX = "ml/time-series-logs/raw/"             # input folder
PROCESSED_PREFIX = "ml/time-series-logs/processed/" # output folder
SEQ_LEN = 30                                       # window length
# ----------------------------

s3 = boto3.client("s3", region_name=AWS_REGION)

# helper to compute distance in km between two geo points
def haversine(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except:
        return 0.0
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.asin(min(1, math.sqrt(a)))

def list_s3_keys(bucket, prefix):
    keys = []
    kwargs = {"Bucket": bucket, "Prefix": prefix}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            keys.append(obj["Key"])
        if resp.get("IsTruncated"):
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        else:
            break
    return keys

# ---------- PASS 1: discover categories ----------
print("🔍 Listing raw files from S3...")
keys = list_s3_keys(S3_BUCKET, RAW_PREFIX)
jsonl_keys = [k for k in keys if k.endswith(".jsonl")]
print(f"Found {len(jsonl_keys)} user files.")

countries=set(); devices=set(); actions=set()

for key in jsonl_keys:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    text = obj["Body"].read().decode("utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines:
        ev = json.loads(line)
        countries.add(ev.get("country","UNK"))
        devices.add(ev.get("device","UNK"))
        actions.add(ev.get("action","UNK"))

map_country = {v:i for i,v in enumerate(sorted(countries))}
map_device  = {v:i for i,v in enumerate(sorted(devices))}
map_action  = {v:i for i,v in enumerate(sorted(actions))}

print("✅ Encoders ready:")
print("Countries:", map_country)
print("Devices:", map_device)
print("Actions:", map_action)

# ---------- PASS 2: build windows ----------
def parse_ts(ts):
    if not ts: return None
    if ts.endswith("Z"): ts = ts.replace("Z","+00:00")
    try:
        return datetime.fromisoformat(ts)
    except:
        return None

windows = []
for key in jsonl_keys:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    text = obj["Body"].read().decode("utf-8")
    events = [json.loads(l) for l in text.splitlines() if l.strip()]
    if len(events) < SEQ_LEN: 
        continue
    feats = []
    prev_lat=None; prev_lon=None
    for ev in events:
        dt = parse_ts(ev.get("timestamp"))
        hour = dt.hour if dt else 0
        dow = dt.weekday() if dt else 0
        country_idx = map_country.get(ev.get("country","UNK"),0)
        device_idx  = map_device.get(ev.get("device","UNK"),0)
        action_idx  = map_action.get(ev.get("action","UNK"),0)
        dl5 = float(ev.get("downloads_last_5m",0))
        dl1h = float(ev.get("downloads_last_1h",0))
        lat = ev.get("lat",0.0); lon = ev.get("lon",0.0)
        geo = 0.0 if prev_lat is None else haversine(prev_lat, prev_lon, lat, lon)
        prev_lat, prev_lon = lat, lon
        feats.append([hour,dow,country_idx,device_idx,action_idx,dl5,dl1h,geo])
    for i in range(SEQ_LEN,len(feats)+1):
        windows.append(np.array(feats[i-SEQ_LEN:i],dtype=np.float32))

X = np.stack(windows, axis=0)
print("🎉 Built dataset:", X.shape)

np.save("X.npy", X)
with open("encoders.pkl","wb") as f:
    pickle.dump({
        "map_country": map_country,
        "map_device": map_device,
        "map_action": map_action,
        "feature_order": ["hour","dow","country","device","action","dl5","dl1h","geo"],
        "seq_len": SEQ_LEN
    }, f)

print("💾 Saved locally: X.npy, encoders.pkl")

# upload back to S3
s3.upload_file("X.npy", S3_BUCKET, PROCESSED_PREFIX+"X.npy")
s3.upload_file("encoders.pkl", S3_BUCKET, PROCESSED_PREFIX+"encoders.pkl")
print(f"☁️ Uploaded to s3://{S3_BUCKET}/{PROCESSED_PREFIX}")
