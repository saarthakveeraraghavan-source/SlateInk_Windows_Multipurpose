"""CPU/CUDA comparison using public and generated fixtures, never a camera."""
from pathlib import Path
import sys,json,time,statistics
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from slateink.paper_ocr import PaperRecognizer

ROOT=Path(__file__).resolve().parent.parent
image=Image.new("RGB",(1000,250),"white")
font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",55)
draw=ImageDraw.Draw(image)
draw.text((40,20),"Hello world",font=font,fill="black")
draw.text((40,130),"Differentiate velocity",font=font,fill="black")
fixtures=[("public-handwriting",np.array(Image.open(ROOT/"artifacts/public-fixture.jpg").convert("RGB")),"industrie"),
          ("synthetic-two-lines",np.array(image),"Hello world Differentiate velocity")]
rows=[]
for variant in ("medium","english"):
    for device in ("cpu","cuda"):
        start=time.perf_counter();model=PaperRecognizer(variant,device)
        cold=time.perf_counter()-start
        for name,rgb,expected in fixtures:
            model.recognize(rgb)
            values=[];texts=[]
            for _ in range(10):
                result=model.recognize(rgb);values.append(result.latency_seconds*1000);texts.append(result.text)
            row={"variant":variant,"requested_device":device,"actual_device":model.device,"fixture":name,
                 "cold_load_and_warmup_seconds":cold,"median_ms":statistics.median(values),
                 "p90_ms":float(np.percentile(values,90)),"repeat_count":10,"exact_match_all":all(t==expected for t in texts)}
            rows.append(row);print(json.dumps(row),flush=True)
        del model
        # Profile a separate session: profiler overhead must not be counted in
        # the user-facing timing comparison.
        model=PaperRecognizer(variant,device,profile=True)
        model.recognize(fixtures[0][1])
        profile_path=Path(model.session.end_profiling())
        profile=json.loads(profile_path.read_text(encoding="utf-8"))
        providers={}
        for event in profile:
            provider=event.get("args",{}).get("provider")
            if provider:providers[provider]=providers.get(provider,0)+1
        print(json.dumps({"variant":variant,"device":device,"executed_kernel_providers":providers}),flush=True)
        for row in rows:
            if row["variant"]==variant and row["requested_device"]==device:row["executed_kernel_providers"]=providers
        if device=="cuda" and not providers.get("CUDAExecutionProvider"):raise RuntimeError("No CUDA kernels executed")
        profile_path.unlink() # Public fixture trace only; preserve aggregate evidence.
        del model
ROOT.joinpath("artifacts/gpu-benchmark.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
if not all(row["exact_match_all"] for row in rows):raise RuntimeError("Fixture output differed")
