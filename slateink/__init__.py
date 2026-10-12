"""SlateInk: visible, local-only finger handwriting input."""
import os
from pathlib import Path

# Keep incidental dependency caches inside the project rather than the user's
# profile. These contain library metadata only, never camera/handwriting data.
_cache = Path(__file__).resolve().parent.parent / "artifacts" / "library-cache"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache / "matplotlib"))
os.environ.setdefault("HF_HOME", str(_cache / "huggingface"))
os.environ.setdefault("CUDA_CACHE_PATH",str(_cache / "cuda"))
__version__ = "0.1.0"
