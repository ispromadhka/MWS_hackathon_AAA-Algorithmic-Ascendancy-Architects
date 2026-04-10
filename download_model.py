#!/usr/bin/env python3
"""Download the LLM model. Run this before starting the server."""

import os
import sys

def main():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Installing huggingface-hub...")
        os.system(f"{sys.executable} -m pip install huggingface-hub")
        from huggingface_hub import hf_hub_download

    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(model_dir, exist_ok=True)

    # Try Q5_K_M first (better quality), fall back to Q4_K_M (smaller)
    variants = [
        ("qwen2.5-coder-7b-instruct-q5_k_m.gguf", "5.4 GB — best quality"),
        ("qwen2.5-coder-7b-instruct-q4_k_m.gguf", "4.7 GB — smaller, faster"),
    ]

    for filename, desc in variants:
        target = os.path.join(model_dir, filename)
        if os.path.exists(target):
            size_gb = os.path.getsize(target) / 1e9
            print(f"Model already exists: {filename} ({size_gb:.1f} GB)")
            return

    # Download the preferred variant
    use_q4 = "--q4" in sys.argv
    filename, desc = variants[1] if use_q4 else variants[0]
    target = os.path.join(model_dir, filename)

    print(f"Downloading {filename} ({desc})...")
    print("This may take 5-15 minutes depending on your connection.")

    hf_hub_download(
        repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename=filename,
        local_dir=model_dir,
    )

    size_gb = os.path.getsize(target) / 1e9
    print(f"Done! Model saved to {target} ({size_gb:.1f} GB)")


if __name__ == "__main__":
    main()
