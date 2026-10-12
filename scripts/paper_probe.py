"""Compare public and synthetic paper OCR fixtures offline. No webcam capture."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from slateink.paper_ocr import PaperRecognizer

rows=[]
font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",55)
synthetic=Image.new("RGB",(1000,250),"white")
draw=ImageDraw.Draw(synthetic)
draw.text((40,20),"Hello world",font=font,fill="black")
draw.text((40,130),"Differentiate velocity",font=font,fill="black")
for name in ("english","medium"):
    model=PaperRecognizer(name)
    for fixture,image,expected in (
        ("public-handwriting",Image.open("artifacts/public-fixture.jpg").convert("RGB"),"industrie"),
        ("synthetic-two-lines",synthetic,"Hello world Differentiate velocity")):
        try:
            result=model.recognize(np.array(image))
            row={"variant":name,"fixture":fixture,"expected":expected,"recognized":result.text,
                 "score_uncalibrated":result.score,"latency_seconds":result.latency_seconds,
                 "exact_match":expected==result.text}
        except Exception as exc:
            row={"variant":name,"fixture":fixture,"error":str(exc)}
        rows.append(row);print(json.dumps(row),flush=True)
Path("artifacts/paper-probe.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
