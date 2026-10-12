"""Explicit public OCR asset installation, separate from offline runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import yaml

ROOT=Path(__file__).resolve().parent.parent
REPOS={"english":"PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx",
       "medium":"PaddlePaddle/PP-OCRv6_medium_rec_onnx"}
REVISIONS={"english":"3fafbc3b5dcf93dd72add9f48368be8a3a2cd33b",
           "medium":"50c7eacafc52fa7bcf4194e8cd08e46f8558504b"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--inspect",action="store_true")
    args=parser.parse_args()
    for name,repo in REPOS.items():
        revision=REVISIONS[name]
        base=f"https://huggingface.co/{repo}/resolve/{revision}/"
        with urllib.request.urlopen(base+"inference.yml",timeout=30) as response:
            config_bytes=response.read()
        config=yaml.safe_load(config_bytes)
        print(name,revision,flush=True)
        print("Preprocess:",config.get("PreProcess"),flush=True)
        post=config.get("PostProcess",{})
        print("Decoder:",post.get("name"),"characters:",len(post.get("character_dict",[])),flush=True)
        if args.inspect:continue
        directory=ROOT/"models"/"paper"/name
        directory.mkdir(parents=True,exist_ok=True)
        (directory/"inference.yml").write_bytes(config_bytes)
        target=directory/"inference.onnx"
        if not target.exists():
            print("Downloading",repo,"...",flush=True)
            partial=target.with_suffix(".onnx.part")
            with urllib.request.urlopen(base+"inference.onnx",timeout=120) as source,partial.open("wb") as output:
                while block:=source.read(1024*1024):output.write(block)
            partial.replace(target)
        manifest={"repository":repo,"revision":revision,"license":"Apache-2.0",
                  "sha256":{file.name:hashlib.sha256(file.read_bytes()).hexdigest()
                            for file in (target,directory/"inference.yml")}}
        (directory/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print("Installed",name,target.stat().st_size,"bytes",flush=True)


if __name__=="__main__":main()
