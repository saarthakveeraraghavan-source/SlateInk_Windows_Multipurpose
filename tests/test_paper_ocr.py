import numpy as np
import pytest
from PIL import Image,ImageDraw,ImageFont
from slateink.calibration import Surface
from slateink.paper_ocr import warp_paper,line_regions,decode_ctc,PaperRecognizer
from slateink.config import ROOT


def test_paper_warp_undoes_preview_mirror():
    image=np.full((100,200,3),255,np.uint8);image[20:80,20:40]=0
    surface=Surface.from_corners([(0,0),(1,0),(1,1),(0,1)])
    correct=warp_paper(image,surface,False)
    flipped=warp_paper(image[:,::-1].copy(),surface,True)
    assert np.allclose(correct,flipped)


def test_multiple_lines_keep_top_to_bottom_order():
    image=Image.new("RGB",(800,240),"white")
    font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",45)
    draw=ImageDraw.Draw(image);draw.text((20,10),"Hello",font=font,fill="black")
    draw.text((20,120),"World",font=font,fill="black")
    lines=line_regions(np.array(image))
    assert len(lines)==2
    assert lines[0].shape[0]>20 and lines[1].shape[0]>20


def test_blank_paper_fails_before_model():
    with pytest.raises(ValueError):line_regions(np.full((200,300,3),255,np.uint8))


def test_ctc_decoding_preserves_repeated_letters_separated_by_blank():
    classes=["","a","b"," "]
    output=np.eye(4,dtype=np.float32)[[1,1,0,1,2,2,3]][None]
    text,score=decode_ctc(output,classes)
    assert text=="aab " and score==1


def test_ctc_bad_dictionary_or_nonfinite_output_rejected():
    with pytest.raises(ValueError):decode_ctc(np.zeros((1,4,4)),["","a"])
    with pytest.raises(ValueError):decode_ctc(np.full((1,4,2),np.nan),["","a"])


def test_dark_slate_can_be_inverted_for_ocr():
    image=Image.new("RGB",(600,150),"black")
    font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",50)
    ImageDraw.Draw(image).text((20,20),"Hello",font=font,fill="white")
    assert len(line_regions(np.array(image),True))==1


def test_local_paper_model_reads_public_handwriting():
    if not (ROOT/"models/paper/medium/inference.onnx").exists():pytest.skip("Install paper models")
    if not (ROOT/"artifacts/public-fixture.jpg").exists():pytest.skip("Public handwriting fixture is unavailable")
    image=np.array(Image.open(ROOT/"artifacts/public-fixture.jpg").convert("RGB"))
    result=PaperRecognizer().recognize(image)
    assert result.text=="industrie" and 0<=result.score<=1
