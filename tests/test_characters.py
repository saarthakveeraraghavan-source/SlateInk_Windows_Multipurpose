import numpy as np
import pytest
from PIL import Image,ImageDraw
from slateink.characters import prepare_character,CharacterRecognizer
from slateink.config import ROOT


def test_single_narrow_vertical_letter_is_not_rejected_as_blank():
    image=Image.new("L",(600,600),255)
    ImageDraw.Draw(image).line([(300,200),(300,450)],fill=0,width=5)
    tensor=prepare_character(image)
    assert tensor.shape==(1,1,96,96) and tensor.dtype==np.float32
    assert tensor.min()>=-1 and tensor.max()<=1
    assert tensor[0,0,0,0]==-1


def test_empty_character_rejected_before_inference():
    with pytest.raises(ValueError):prepare_character(Image.new("L",(600,600),255))


def test_character_centers_and_keeps_aspect_ratio():
    image=Image.new("L",(600,600),255)
    ImageDraw.Draw(image).line([(110,210),(110,450)],fill=0,width=8)
    data=prepare_character(image)[0,0]
    ys,xs=np.where(data>0)
    assert abs(xs.mean()-47.5)<2 and abs(ys.mean()-47.5)<2
    assert np.ptp(xs)<np.ptp(ys)/5


def test_real_alphabet_model_is_local_and_returns_one_letter():
    if not (ROOT/"models/alphabet/alphabet_model.onnx").exists():pytest.skip("Install alphabet model")
    image=Image.new("L",(300,300),255)
    ImageDraw.Draw(image).line([(80,240),(150,50),(220,240)],fill=0,width=12)
    ImageDraw.Draw(image).line([(107,160),(192,160)],fill=0,width=12)
    result=CharacterRecognizer().recognize(image)
    assert len(result.text)==1 and result.text in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert 0<=result.score<=1 and len(result.alternatives)==3
