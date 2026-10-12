"""One-time alphabet asset download; no private data or remote code execution."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
REVISION="cf2bb20a6606fa405afb8f0b3df986c22169760f"
REPO="hermitkk/alphabet-classifier"
FILE="outputs/exports/alphabet_model.onnx"


def main():
    directory=ROOT/"models"/"alphabet"
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/"alphabet_model.onnx"
    if not target.exists():
        partial=target.with_suffix(".onnx.part")
        url=f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILE}"
        print("Downloading single-letter model...",flush=True)
        with urllib.request.urlopen(url,timeout=120) as source,partial.open("wb") as output:
            while block:=source.read(1024*1024):output.write(block)
        partial.replace(target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    manifest={"repository":REPO,"revision":REVISION,"filename":FILE,
              "sha256":digest,"license":"MIT","classes":list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")+["blank"]}
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("Alphabet model ready:",target.stat().st_size,"bytes",flush=True)


if __name__=="__main__":main()
