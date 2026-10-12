"""One-time local face/iris asset download. No biometric data is uploaded."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
SHA256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

def main():
    root=ROOT/"models/eyes";root.mkdir(parents=True,exist_ok=True)
    target=root/"face_landmarker.task"
    if not target.exists():
        with urllib.request.urlopen(URL,timeout=120) as source:data=source.read()
        if hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError("Downloaded eye model integrity failed.")
        target.write_bytes(data)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=SHA256:raise ValueError("Local eye model integrity failed.")
    (root/"manifest.json").write_text(json.dumps({"url":URL,"sha256":hashlib.sha256(target.read_bytes()).hexdigest()},indent=2),encoding="utf-8")
    print("Local face/iris model installed:",target.stat().st_size,"bytes")
if __name__=="__main__":main()
