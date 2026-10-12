"""Local synthetic-glyph benchmark; not a finger-handwriting accuracy claim."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from slateink.characters import CharacterRecognizer,prepare_character

model=CharacterRecognizer()
font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",100)
rows=[]
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
    image=Image.new("L",(180,180),255)
    ImageDraw.Draw(image).text((25,5),char,font=font,fill=0)
    tensor=prepare_character(image)
    for mode,data in (("white_ink_on_black",tensor),("black_ink_on_white",-tensor)):
        start=time.perf_counter()
        model.net.setInput(data)
        logits=model.net.forward().reshape(-1)
        probabilities=np.exp(logits-logits.max()); probabilities/=probabilities.sum()
        best=int(probabilities.argmax())
        prediction="ABCDEFGHIJKLMNOPQRSTUVWXYZ"[best] if best<26 else "blank"
        rows.append({"glyph":char,"mode":mode,"prediction":prediction,"score":float(probabilities[best]),
                     "correct":prediction==char.upper(),"latency_ms":(time.perf_counter()-start)*1000})
summary={mode:{"correct":sum(row["correct"] for row in rows if row["mode"]==mode),
               "samples":52,"median_ms":float(np.median([row["latency_ms"] for row in rows if row["mode"]==mode]))}
         for mode in ("white_ink_on_black","black_ink_on_white")}
summary["scope"]="Synthetic printed glyphs only; physical finger handwriting unvalidated"
Path("artifacts/character-probe.json").write_text(json.dumps({"summary":summary,"rows":rows},indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
for row in rows:
    if row["mode"]=="white_ink_on_black" and not row["correct"]:
        print("Synthetic glyph mismatch:",row["glyph"],"->",row["prediction"])
