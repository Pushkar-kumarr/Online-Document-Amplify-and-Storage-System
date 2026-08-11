# lambda_function.py
import boto3, json, os, pickle, tempfile
from datetime import datetime
from botocore.exceptions import ClientError

# ENV vars (set these on Lambda configuration)
ENDPOINT = os.environ.get("ENDPOINT", "secure-doc-anomaly-endpoint")
S3_BUCKET = os.environ.get("S3_BUCKET", "secure-ml-pushkar-2025")
ENCODERS_KEY = os.environ.get("ENCODERS_KEY", "ml/model/encoders.pkl")
MODEL_META_KEY = os.environ.get("MODEL_META_KEY", "ml/model/model_meta.pkl")
DDB_TABLE = os.environ.get("DDB_TABLE", "AccessLogs")
SEQ_LEN = int(os.environ.get("SEQ_LEN", "30"))

sagemaker_runtime = boto3.client("sagemaker-runtime")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DDB_TABLE)

# cached global
_encoders = None
_threshold = None

def load_encoders_and_meta():
    global _encoders, _threshold
    if _encoders is not None:
        return _encoders, _threshold
    # download encoders
    tmp_enc = "/tmp/encoders.pkl"
    try:
        s3.download_file(S3_BUCKET, ENCODERS_KEY, tmp_enc)
        with open(tmp_enc, "rb") as f:
            _encoders = pickle.load(f)
    except Exception as e:
        raise RuntimeError("Failed to load encoders from S3: " + str(e))
    # download model_meta if present
    tmp_meta = "/tmp/model_meta.pkl"
    try:
        s3.download_file(S3_BUCKET, MODEL_META_KEY, tmp_meta)
        with open(tmp_meta, "rb") as f:
            meta = pickle.load(f)
            _threshold = meta.get("threshold")
    except Exception:
        _threshold = None
    return _encoders, _threshold

def query_last_events(user_id, limit=SEQ_LEN):
    resp = table.query(
        KeyConditionExpression = boto3.dynamodb.conditions.Key('user_id').eq(user_id),
        ScanIndexForward = False,
        Limit = limit
    )
    items = resp.get("Items", [])
    # sort ascending by timestamp (oldest first)
    items = sorted(items, key=lambda x: x['timestamp'])
    return items

def event_to_features(ev, enc):
    # Feature order: hour, day_of_week, country_idx, device_idx, action_idx, dl5, dl1h, geo
    ts = ev.get("timestamp")
    try:
        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        else:
            dt = datetime.fromisoformat(ts)
        hour = dt.hour
        dow = dt.weekday()
    except:
        hour = 0; dow = 0
    country_idx = enc['map_country'].get(ev.get('country',"UNK"), 0)
    device_idx  = enc['map_device'].get(ev.get('device',"UNK"), 0)
    action_idx  = enc['map_action'].get(ev.get('action',"UNK"), 0)
    try:
        dl5 = float(ev.get('downloads_last_5m', 0))
    except:
        dl5 = 0.0
    try:
        dl1h = float(ev.get('downloads_last_1h', 0))
    except:
        dl1h = 0.0
    geo = 0.0
    return [hour, dow, country_idx, device_idx, action_idx, dl5, dl1h, geo]

def build_sequence(user_id):
    enc, _ = load_encoders_and_meta()
    evs = query_last_events(user_id, SEQ_LEN)
    feats = [event_to_features(e, enc) for e in evs]
    if len(feats) < SEQ_LEN:
        pad = [[0.0]*8 for _ in range(SEQ_LEN - len(feats))]
        feats = pad + feats
    return feats

def call_model(sequence_batch):
    payload = json.dumps({"instances": sequence_batch})
    resp = sagemaker_runtime.invoke_endpoint(
        EndpointName=ENDPOINT, ContentType="application/json", Body=payload
    )
    out = json.loads(resp["Body"].read().decode())
    return out

def lambda_handler(event, context):
    user_id = event.get("user_id")
    if not user_id:
        return {"statusCode":400, "body": json.dumps({"error":"user_id required"})}
    enc, threshold = load_encoders_and_meta()
    seq = build_sequence(user_id)
    # call model (batch of 1)
    result = call_model([seq])
    scores = result.get("scores", [])
    remote_threshold = result.get("threshold", None)
    final_threshold = remote_threshold if remote_threshold is not None else threshold
    if not scores:
        return {"statusCode":500, "body": json.dumps({"error":"no scores returned by model"})}
    score = float(scores[0])
    if final_threshold is not None and score > final_threshold:
        # suspicious -> return OTP_REQUIRED (frontend will force signout/relogin)
        return {"statusCode":200, "body": json.dumps({"status":"OTP_REQUIRED","score":score,"threshold":final_threshold})}
    else:
        return {"statusCode":200, "body": json.dumps({"status":"OK","score":score,"threshold":final_threshold})}
