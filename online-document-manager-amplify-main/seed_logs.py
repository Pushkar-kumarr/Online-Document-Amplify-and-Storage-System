import boto3, datetime, random, time
from decimal import Decimal

# ---------- CONFIG ----------
AWS_REGION = "ap-south-1"
DDB_TABLE = "AccessLogs"
USERS = ["userA", "userB", "userC", "userD", "userE"]
EVENTS_PER_USER = 40
# ----------------------------

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DDB_TABLE)

def seed_user(user_id):
    base_time = datetime.datetime.now(datetime.UTC)  # timezone-aware
    for i in range(EVENTS_PER_USER):
        ts = (base_time - datetime.timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        item = {
            "user_id": user_id,
            "timestamp": ts,
            "country": random.choice(["IN", "US", "UK", "DE", "SG"]),
            "device": random.choice(["chrome", "mobile", "firefox", "safari"]),
            "action": random.choice(["login", "download", "view"]),
            "downloads_last_5m": Decimal(random.randint(0, 5)),
            "downloads_last_1h": Decimal(random.randint(0, 20)),
            "lat": Decimal(str(12.9 + random.random())),
            "lon": Decimal(str(77.6 + random.random()))
        }
        table.put_item(Item=item)
    print(f"✅ Seeded {EVENTS_PER_USER} events for {user_id}")

def main():
    for user in USERS:
        seed_user(user)
        time.sleep(0.5)
    print("🎉 Finished seeding all users!")

if __name__ == "__main__":
    main()
