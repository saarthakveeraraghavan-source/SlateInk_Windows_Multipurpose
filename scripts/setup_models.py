"""Explicit online installation, separate from the offline application."""
from pathlib import Path
import hashlib
import json
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
REVISION = "b4648cfa171985a6745f37ddd637e98c0da958ac"
REPO = "microsoft/trocr-small-handwritten"
FILES = ["config.json", "generation_config.json", "preprocessor_config.json",
         "pytorch_model.bin", "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer_config.json"]
HAND_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def download(url, path):
    if path.exists() and path.stat().st_size:
        print("Present:", path.name, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    print("Downloading:", path.name, flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "SlateInk-setup/0.1"})
    with urllib.request.urlopen(request, timeout=120) as source, partial.open("wb") as target:
        while block := source.read(1024*1024):
            target.write(block)
    partial.replace(path)


def main():
    MODELS.mkdir(exist_ok=True)
    download(HAND_URL, MODELS / "hand_landmarker.task")
    directory = MODELS / "trocr-small-handwritten"
    directory.mkdir(exist_ok=True)
    safe = directory / "model.safetensors"
    for name in FILES:
        if name == "pytorch_model.bin" and safe.exists():
            continue
        download(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}", directory / name)
    if not safe.exists():
        import torch
        from safetensors.torch import save_file
        print("Converting weights with restricted weights_only loading...", flush=True)
        weights = torch.load(directory / "pytorch_model.bin", map_location="cpu", weights_only=True)
        # Clone tied tensors so safetensors never serializes shared storage.
        save_file({key: tensor.contiguous().clone() for key, tensor in weights.items()}, str(safe))
    # Remove only this installer's redundant model asset after successful conversion.
    original = directory / "pytorch_model.bin"
    if original.exists() and safe.exists():
        original.unlink()
    paths = [MODELS / "hand_landmarker.task"] + sorted(p for p in directory.iterdir() if p.is_file())
    manifest = {"model_repository": REPO, "revision": REVISION,
                "hand_model_url": HAND_URL,
                "sha256": {p.relative_to(MODELS).as_posix(): digest(p) for p in paths}}
    (MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Local models ready. Normal application use needs no internet.", flush=True)


if __name__ == "__main__":
    main()
