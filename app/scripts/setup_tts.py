#!/usr/bin/env python3
import os
import urllib.request
import subprocess
import sys

def download_file(url, filename):
    if os.path.exists(filename):
        print(f"File already exists: {filename}")
        return
    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, filename)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        sys.exit(1)

def setup_kokoro():
    print("Checking Kokoro ONNX models...")
    base_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/v0.1.0"
    download_file(f"{base_url}/kokoro-v1.0.onnx", "kokoro-v1.0.onnx")
    download_file(f"{base_url}/voices-v1.0.bin", "voices-v1.0.bin")

def setup_unidic():
    print("Checking UniDic...")
    # Check if unidic is usable
    try:
        import unidic
        dic_dir = unidic.DICDIR
        mecabrc = os.path.join(dic_dir, "mecabrc")
        if os.path.exists(mecabrc):
            print(f"UniDic seems installed at {dic_dir}")
            return
    except ImportError:
        pass

    print("Installing UniDic dictionary...")
    try:
        subprocess.check_call([sys.executable, "-m", "unidic", "download"])
        print("UniDic setup complete.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install UniDic: {e}")
        # Dont exit, might work if already installed but check failed

if __name__ == "__main__":
    setup_kokoro()
    setup_unidic()
