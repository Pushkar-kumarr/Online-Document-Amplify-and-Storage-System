import torch
import torch.nn as nn
import io
import json
import numpy as np
import pickle

# --- Use the same TransformerAutoencoder class as in training ---
class TransformerAutoencoder(nn.Module):
    def __init__(self, seq_len, n_features, hidden_dim=64, n_heads=4, n_layers=2):
        super().__init__()
        self.encoder_layer = nn.TransformerEncoderLayer(d_model=n_features, nhead=n_heads, dim_feedforward=hidden_dim)
        self.encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=n_layers)
        self.decoder_layer = nn.TransformerDecoderLayer(d_model=n_features, nhead=n_heads, dim_feedforward=hidden_dim)
        self.decoder = nn.TransformerDecoder(self.decoder_layer, num_layers=n_layers)

    def forward(self, x):
        # x: (batch, seq, features)
        x = x.permute(1, 0, 2)  # (seq, batch, features)
        encoded = self.encoder(x)
        decoded = self.decoder(encoded, encoded)
        decoded = decoded.permute(1, 0, 2)
        return decoded

# ---- model_fn called by SageMaker to load model objects ----
def model_fn(model_dir):
    # model_dir is the folder containing model artifacts (the .pt file + metadata)
    import os
    model_path = os.path.join(model_dir, "transformer_autoencoder.pt")
    meta_path = os.path.join(model_dir, "model_meta.pkl")
    encoders_path = os.path.join(model_dir, "encoders.pkl")

    # load encoders/metadata
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    with open(encoders_path, "rb") as f:
        enc = pickle.load(f)

    seq_len = meta.get("seq_len", 30)   # if your meta doesn't include seq_len, default 30
    # try to infer n_features from encoders feature_order length or fallback to 8
    n_features = 8
    if "feature_order" in enc:
        # hour,dow,country,device,action,dl5,dl1h,geo -> 8 features
        n_features = len(enc["feature_order"])

    # create model instance and load weights
    model = TransformerAutoencoder(seq_len, n_features, hidden_dim=64)
    state_dict = torch.load(model_path, map_location=torch.device("cpu"))
    # If you saved state_dict, call load_state_dict
    try:
        model.load_state_dict(state_dict)
    except Exception:
        # maybe you saved full model, try direct load
        model = state_dict

    model.eval()

    # bundle objects for use in predict_fn
    return {"model": model, "meta": meta, "encoders": enc}

# ---- input_fn: parse request payload into numpy array (or torch tensor) ----
def input_fn(request_body, request_content_type):
    # Expect JSON with key "instances": a list of sequences (each is seq x features)
    if request_content_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict) and "instances" in payload:
            arr = np.array(payload["instances"], dtype=np.float32)
            # Ensure shape (batch, seq, features)
            return arr
        else:
            # assume payload is a raw 3D array
            return np.array(payload, dtype=np.float32)
    else:
        raise ValueError("Unsupported content type: " + request_content_type)

# ---- predict_fn: compute reconstruction error (MSE per sequence) ----
def predict_fn(input_data, model_bundle):
    # input_data: numpy array shape (batch, seq, features)
    model = model_bundle["model"]
    meta = model_bundle["meta"]
    # convert to torch
    x = torch.tensor(input_data, dtype=torch.float32)
    with torch.no_grad():
        recon = model(x)
        mse = ((recon - x) ** 2).mean(dim=(1,2)).cpu().numpy().tolist()
    # return list of scores
    return {"scores": mse, "threshold": meta.get("threshold", None)}

# ---- output_fn: format response ----
def output_fn(prediction, content_type):
    if content_type == "application/json":
        return json.dumps(prediction), "application/json"
    else:
        raise ValueError("Unsupported content type: " + content_type)
