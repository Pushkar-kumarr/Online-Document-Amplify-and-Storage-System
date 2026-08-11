# toggle_sagemaker.py
import boto3
from sagemaker.pytorch import PyTorchModel
import sagemaker
from botocore.exceptions import ClientError

# ---------- CONFIG ----------
ENDPOINT_NAME = "secure-doc-anomaly-endpoint"
ROLE = "arn:aws:iam::980853423458:role/SageMakerRole_SecDocs"
MODEL_S3_PATH = "s3://secure-ml-pushkar-2025/ml/model/model.tar.gz"
# ----------------------------

sm = boto3.client("sagemaker")
sagemaker_session = sagemaker.Session()

def endpoint_exists(name):
    """Check if the endpoint exists."""
    try:
        sm.describe_endpoint(EndpointName=name)
        return True
    except ClientError as e:
        if "Could not find" in str(e) or "does not exist" in str(e):
            return False
        raise

def stop_endpoint():
    """Delete endpoint and its configs to stop costs."""
    print("🛑 Stopping SageMaker endpoint...")

    try:
        sm.delete_endpoint(EndpointName=ENDPOINT_NAME)
        print("✅ Endpoint deleted.")
    except Exception as e:
        print("⚠️ Could not delete endpoint:", e)

    try:
        sm.delete_endpoint_config(EndpointConfigName=ENDPOINT_NAME + "-config")
        print("✅ Endpoint configuration deleted.")
    except Exception as e:
        print("⚠️ Could not delete endpoint config:", e)

    try:
        sm.delete_model(ModelName=ENDPOINT_NAME)
        print("✅ Model deleted.")
    except Exception as e:
        print("⚠️ Could not delete model:", e)

def start_endpoint():
    """Redeploy the model from S3 to SageMaker."""
    print("🚀 Starting SageMaker endpoint...")

    try:
        pytorch_model = PyTorchModel(
            model_data=MODEL_S3_PATH,
            role=ROLE,
            entry_point="inference.py",
            source_dir=".",
            framework_version="2.0.0",
            py_version="py310",
            sagemaker_session=sagemaker_session,
        )

        predictor = pytorch_model.deploy(
            initial_instance_count=1,
            instance_type="ml.m5.large",
            endpoint_name=ENDPOINT_NAME
        )

        print("✅ Endpoint redeployed and ready for demo!")
    except Exception as e:
        print("❌ Deployment failed:", e)

if __name__ == "__main__":
    print("🔍 Checking SageMaker endpoint status...")
    if endpoint_exists(ENDPOINT_NAME):
        print(f"✅ Endpoint '{ENDPOINT_NAME}' is currently ACTIVE.")
        choice = input("Do you want to stop it to save cost? (y/n): ").strip().lower()
        if choice == "y":
            stop_endpoint()
        else:
            print("ℹ️ Keeping endpoint running.")
    else:
        print(f"⚠️ Endpoint '{ENDPOINT_NAME}' not found.")
        choice = input("Do you want to deploy it now? (y/n): ").strip().lower()
        if choice == "y":
            start_endpoint()
        else:
            print("ℹ️ No action taken.")
