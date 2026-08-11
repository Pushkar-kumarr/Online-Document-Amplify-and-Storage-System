import boto3, json, time
from collections import defaultdict
from botocore.exceptions import ClientError

# 🔹 Your details
AWS_REGION = "ap-south-1"                      # change if your region is different
DDB_TABLE = "AccessLogs"                       # DynamoDB table name
S3_BUCKET = "secure-ml-pushkar-2025"           # ✅ your S3 bucket
S3_PREFIX = "ml/time-series-logs/raw/"         # folder in S3

session = boto3.Session(region_name=AWS_REGION)
dynamodb = session.resource("dynamodb")
table = dynamodb.Table(DDB_TABLE)
s3 = session.client("s3")

def scan_all_items():
    last_key = None
    while True:
        if last_key:
            resp = table.scan(ExclusiveStartKey=last_key)
        else:
            resp = table.scan()
        for it in resp.get("Items", []):
            yield it
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break

def flush_to_s3(by_user):
    for uid, events in by_user.items():
        events_sorted = sorted(events, key=lambda x: x.get("timestamp",""))
        body = "\n".join(json.dumps(e, default=str) for e in events_sorted)
        key = f"{S3_PREFIX}{uid}.jsonl"
        try:
            s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body.encode("utf-8"))
            print("✅ wrote", key)
        except ClientError as e:
            print("❌ error uploading", key, e)

def main():
    by_user = defaultdict(list)
    count = 0
    for item in scan_all_items():
        uid = item.get("user_id")
        if not uid:
            continue
        by_user[uid].append(item)
        count += 1
    if by_user:
        flush_to_s3(by_user)
    print("🎉 Export finished. Total logs:", count)

if __name__ == "__main__":
    main()
