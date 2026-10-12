import hashlib
import json
from pathlib import Path
import pytest
from slateink import models


def test_model_checks_portable_manifest_keys(tmp_path,monkeypatch):
    monkeypatch.setattr(models,"ROOT",tmp_path)
    assets=tmp_path/"models"
    file=assets/"trocr-small-handwritten"/"config.json"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"safe fixture")
    manifest={"revision":"b4648cfa171985a6745f37ddd637e98c0da958ac",
              "sha256":{"trocr-small-handwritten/config.json":hashlib.sha256(file.read_bytes()).hexdigest()}}
    (assets/"manifest.json").write_text(json.dumps(manifest))
    models.verify_assets(["trocr-small-handwritten/config.json"])
    file.write_bytes(b"corrupted fixture")
    with pytest.raises(ValueError,match="integrity"):
        models.verify_assets(["trocr-small-handwritten/config.json"])


def test_installed_model_assets_match_manifest():
    if not (models.ROOT/"models"/"manifest.json").exists():
        pytest.skip("Install models to run integrity integration check")
    models.verify_assets(models.HAND_FILES+models.RECOGNITION_FILES)
