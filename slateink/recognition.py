from dataclasses import dataclass
import math
import time
from PySide6.QtCore import QThread, Signal
from .config import ROOT
from .rendering import prepare_line


@dataclass(frozen=True)
class Recognition:
    text: str
    score: float | None
    latency_seconds: float
    truncated: bool = False
    alternatives: tuple = ()
    device: str = "CPU"


class LocalRecognizer:
    def __init__(self, device="cpu"):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        from transformers.utils import logging as transformer_logging
        transformer_logging.set_verbosity_error()
        directory = ROOT / "models" / "trocr-small-handwritten"
        if not (directory / "model.safetensors").exists():
            raise FileNotFoundError("Local handwriting model missing. Run scripts/setup_models.py once.")
        from .models import verify_assets,RECOGNITION_FILES
        verify_assets(RECOGNITION_FILES)
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but this PyTorch installation has no CUDA device. Set recognition_device to cpu.")
        torch.set_num_threads(4)
        self.torch, self.device = torch, device
        self.processor = TrOCRProcessor.from_pretrained(str(directory), local_files_only=True, use_fast=False)
        self.model = VisionEncoderDecoderModel.from_pretrained(
            str(directory), local_files_only=True, use_safetensors=True).to(device).eval()

    def recognize(self, image):
        start = time.perf_counter()
        prepared = prepare_line(image)
        with self.torch.inference_mode():
            pixels = self.processor(images=prepared, return_tensors="pt").pixel_values.to(self.device)
            output = self.model.generate(pixels, max_new_tokens=96, num_beams=1,
                                         return_dict_in_generate=True, output_scores=True)
            tokens = output.sequences[0]
            text = self.processor.batch_decode(output.sequences, skip_special_tokens=True)[0].strip()
            transitions = self.model.compute_transition_scores(output.sequences, output.scores, normalize_logits=True)[0]
            generated = tokens[-len(transitions):]
            specials = set(self.processor.tokenizer.all_special_ids)
            probabilities = [float(score) for token, score in zip(generated, transitions) if int(token) not in specials]
            score = math.exp(sum(probabilities)/len(probabilities)) if probabilities else None
            eos = self.model.generation_config.eos_token_id
            eos = set(eos if isinstance(eos, list) else [eos])
            truncated = not any(int(t) in eos for t in generated)
        if not text:
            raise ValueError("The recognizer returned no text. Adjust the strokes and retry.")
        return Recognition(text, score, time.perf_counter()-start, truncated)


class RecognitionWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, image, device, existing=None):
        super().__init__()
        self.image, self.device, self.recognizer = image, device, existing

    def run(self):
        try:
            if self.recognizer is None:
                from .characters import CharacterRecognizer
                self.recognizer = CharacterRecognizer()
            result = self.recognizer.recognize(self.image)
            if not self.isInterruptionRequested():
                self.ready.emit(result)
        except Exception:
            if not self.isInterruptionRequested():
                # Exception strings may contain model-generated content. Keep logs/UI generic.
                self.failed.emit("Letter recognition failed or found no usable letter. Write one letter, retry, or clear it. No text was sent.")
        finally:
            self.image = None
