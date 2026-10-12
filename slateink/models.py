"""Verify only explicitly known local assets against installation hashes."""
import hashlib
import json
from .config import ROOT

HAND_FILES = ["hand_landmarker.task"]
RECOGNITION_FILES = ["trocr-small-handwritten/" + name for name in (
    "config.json", "generation_config.json", "preprocessor_config.json",
    "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer_config.json", "model.safetensors")]


def verify_assets(files):
    root=ROOT/"models"
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("revision") != "b4648cfa171985a6745f37ddd637e98c0da958ac":
        raise ValueError("Unexpected handwriting model revision. Reinstall local models.")
    for name in files:
        path=root/name
        checksum=hashlib.sha256()
        with path.open("rb") as asset:
            for block in iter(lambda:asset.read(1024*1024),b""):
                checksum.update(block)
        if checksum.hexdigest()!=manifest["sha256"].get(name):
            raise ValueError("Local model integrity check failed. Reinstall assets with the setup script.")
