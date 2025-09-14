import os
import shutil
import random

# === CONFIG ===
src_folder = "/home/quannh/Downloads/Tempo_Run/train"   # Path to your dataset
output_folder = "dataset"      # Where to create train/public/private
split_counts = {
    "train": 1500,
    "public": 200,
    "private": 300
}
# ==============

# Create output directories
for split in split_counts.keys():
    os.makedirs(os.path.join(output_folder, split), exist_ok=True)

# List all files
files = [f for f in os.listdir(src_folder) if os.path.isfile(os.path.join(src_folder, f))]
random.shuffle(files)  # Shuffle for randomness

# Check if enough files exist
total_needed = sum(split_counts.values())
if len(files) < total_needed:
    raise ValueError(f"Not enough files! Found {len(files)} but need {total_needed}.")

# Assign files
start = 0
splits = {}
for split, count in split_counts.items():
    end = start + count
    splits[split] = files[start:end]
    start = end

# Copy files
for split, split_files in splits.items():
    for f in split_files:
        shutil.copy2(os.path.join(src_folder, f), os.path.join(output_folder, split, f))

print(f"✅ Done! Split {len(files)} files into:")
for split, split_files in splits.items():
    print(f"  {split}: {len(split_files)} files")
