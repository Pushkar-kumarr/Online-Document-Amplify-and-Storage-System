import sagemaker
from sagemaker.pytorch import PyTorchModel
import boto3

sagemaker_session = sagemaker.Session()
role = "arn:aws:iam::980853423458:role/SageMakerRole_SecDocs"   # <-- REPLACE

# S3 location where you uploaded artifacts
model_data_s3 = "s3://secure-ml-pushkar-2025/ml/model/model.tar.gz"

# Create a PyTorchModel object using the inference.py as entry_point
pytorch_model = PyTorchModel(
    model_data=model_data_s3,            # path to model artifacts folder (SageMaker expects tar.gz sometimes)
    role=role,
    entry_point="inference.py",
    source_dir=".",                     # current dir contains inference.py and any code
    framework_version="2.0.0",
    py_version="py310",
    sagemaker_session=sagemaker_session,
)

# Deploy (this will create model, endpoint config and endpoint)
endpoint_name = "secure-doc-anomaly-endpoint"
predictor = pytorch_model.deploy(
    initial_instance_count=1,
    instance_type="ml.m5.large",       # choose ml.m5.large for CPU inference; ml.t3.medium for cheaper tests
    endpoint_name=endpoint_name
)

print("Endpoint deployed:", endpoint_name)
