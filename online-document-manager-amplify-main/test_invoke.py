import boto3, json, numpy as np

client = boto3.client("sagemaker-runtime", region_name="ap-south-1")
endpoint_name = "secure-doc-anomaly-endpoint"

# Load one example window from your X.npy (local)
import numpy as np
X = np.load("X.npy")
sample = X[0:3].tolist()  # batch of 3 sequences

payload = json.dumps({"instances": sample})

resp = client.invoke_endpoint(
    EndpointName=endpoint_name,
    ContentType="application/json",
    Body=payload
)

body = resp["Body"].read().decode()
print("Response:", body)
