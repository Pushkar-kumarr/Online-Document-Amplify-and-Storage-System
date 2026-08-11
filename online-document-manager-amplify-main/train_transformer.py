#!/usr/bin/env python3
"""
train_transformer.py
Train a Transformer Autoencoder to detect unusual access patterns.
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import pickle

# ---------------- CONFIG ----------------
SEQ_LEN = 30       # same as in preprocessing
BATCH_SIZE = 16
EPOCHS = 10
LR = 1e-3
HIDDEN_DIM = 64
# ----------------------------------------

# Load preprocessed data
print("📦 Loading X.npy...")
X = np.load("X.npy")  # shape (N, 30, 8)
X = torch.tensor(X, dtype=torch.float32)
print("✅ Data shape:", X.shape)

# Create Dataset
dataset = TensorDataset(X, X)
loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

# Define Transformer Autoencoder
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

# Initialize model
n_features = X.shape[2]
model = TransformerAutoencoder(SEQ_LEN, n_features, HIDDEN_DIM)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.MSELoss()

# Training loop
print("🚀 Training model...")
for epoch in range(EPOCHS):
    total_loss = 0
    for xb, yb in loader:
        optimizer.zero_grad()
        out = model(xb)
        loss = criterion(out, yb)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"Epoch {epoch+1}/{EPOCHS} — Loss: {total_loss/len(loader):.6f}")

# Save model
torch.save(model.state_dict(), "transformer_autoencoder.pt")
print("💾 Saved model → transformer_autoencoder.pt")

# Evaluate and compute anomaly threshold
model.eval()
with torch.no_grad():
    recon = model(X)
    mse = ((recon - X) ** 2).mean(dim=(1, 2))
    mean_err = mse.mean().item()
    std_err = mse.std().item()
    threshold = mean_err + 2 * std_err
    print(f"📊 Mean reconstruction error: {mean_err:.6f}")
    print(f"🔒 Suggested anomaly threshold: {threshold:.6f}")

# Save metadata
with open("model_meta.pkl", "wb") as f:
    pickle.dump({"threshold": threshold}, f)
print("✅ Saved model metadata → model_meta.pkl")
