"""Offline recognition smoke test on a public/synthetic fixture, no camera."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from PIL import Image
from slateink.recognition import LocalRecognizer


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("image",type=Path)
    parser.add_argument("--expected")
    parser.add_argument("--output",type=Path,default=Path("artifacts/recognition-smoke.json"))
    args=parser.parse_args()
    start=time.perf_counter()
    model=LocalRecognizer()
    loading=time.perf_counter()-start
    with Image.open(args.image) as image:
        result=model.recognize(image)
    metrics={"fixture":args.image.name,"model_load_seconds":loading,
             "recognition_seconds":result.latency_seconds,"model_score_uncalibrated":result.score,
             "truncated":result.truncated,"text":result.text,"offline":True}
    if args.expected:
        metrics["expected"]=args.expected
        metrics["exact_match"]=args.expected==result.text
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2))


if __name__=="__main__":
    main()
