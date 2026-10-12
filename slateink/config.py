from dataclasses import dataclass, fields
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_exposure: int | None = -5
    camera_mirrored: bool = True
    camera_rotation: int = 0
    initial_mode: str = "paper"
    canvas_width: int = 600
    canvas_height: int = 600
    pinch_down_ratio: float = 0.35
    pinch_up_ratio: float = 0.55
    pinch_debounce_ms: int = 60
    typing_delay_seconds: float = 5
    recognition_device: str = "cpu"
    low_score_threshold: float = 0.8
    max_points: int = 40000
    max_text_characters: int = 2000
    touchpad_sensitivity: float = 1.0
    touchpad_deadzone: float = 0.003
    ocr_device: str = "auto"
    gaze_allow_unverified: bool = False
    touchpad_hand: str = "auto"
    touchpad_submode: str = "desktop"
    touchpad_swipe_enabled: bool = True
    touchpad_swipe_sensitivity: float = 1.0
    touchpad_swipe_cooldown: float = .8
    drawing_sensitivity: float = 1.6
    gaming_radius: float = .22
    gaming_hud: bool = True
    drawing_two_hand: bool = False
    touchpad_scroll_speed: float = 24.0
    touchpad_natural_scroll: bool = False
    touchpad_drag_threshold: float = .012
    touchpad_background: bool = True
    wispr_enabled: bool = False
    wispr_shortcut_mode: str = "toggle_ctrl_win"

    def __post_init__(self):
        if not (0 < self.pinch_down_ratio < self.pinch_up_ratio < 2):
            raise ValueError("Pinch release threshold must exceed pinch-down threshold.")
        if not (2 <= self.typing_delay_seconds <= 30):
            raise ValueError("Typing delay must be between 2 and 30 seconds.")
        if self.recognition_device not in {"cpu", "cuda"}:
            raise ValueError("Recognition device must be cpu or cuda.")
        if not (0 <= self.camera_index <= 10 and 0 < self.camera_fps <= 120):
            raise ValueError("Invalid camera settings.")
        if self.camera_exposure is not None and not (-13 <= self.camera_exposure <= 0):
            raise ValueError("Windows exposure must be null or between -13 and 0.")
        if type(self.camera_mirrored) is not bool or self.camera_rotation not in {0,90,180,270}:
            raise ValueError("Invalid camera mirror/rotation settings.")
        if self.initial_mode not in {"paper","hand_mouse","pen_pointer","finger_letters","eye_gaze"}:
            raise ValueError("Invalid initial mode.")
        if not (0.2<=self.touchpad_sensitivity<=3 and 0.001<=self.touchpad_deadzone<=0.02):
            raise ValueError("Invalid touchpad sensitivity/deadzone.")
        if self.ocr_device not in {"auto","cpu","cuda"}:raise ValueError("OCR device must be auto, cpu or cuda.")
        if type(self.gaze_allow_unverified) is not bool:raise ValueError("Unverified gaze choice must be true or false.")
        if self.touchpad_hand not in {"auto","Left","Right"}:raise ValueError("Invalid controlling hand.")
        if self.touchpad_submode not in {"desktop","gaming","drawing"}:raise ValueError("Invalid touchpad sub-mode.")
        if type(self.touchpad_swipe_enabled) is not bool:raise ValueError("Window swipe option must be true or false.")
        if not (.5<=self.touchpad_swipe_sensitivity<=2 and .4<=self.touchpad_swipe_cooldown<=3):raise ValueError("Invalid window swipe sensitivity/cooldown.")
        if any(type(v) is not bool for v in (self.gaming_hud,self.drawing_two_hand)):raise ValueError("Gaming display and two-hand drawing options must be true or false.")
        if not (.2<=self.drawing_sensitivity<=3 and .12<=self.gaming_radius<=.6):raise ValueError("Invalid drawing speed or gaming travel.")
        if not (4<=self.touchpad_scroll_speed<=60 and .004<=self.touchpad_drag_threshold<=.05):raise ValueError("Invalid scroll/drag settings.")
        if any(type(v) is not bool for v in (self.touchpad_natural_scroll,self.touchpad_background,self.wispr_enabled)):raise ValueError("Touchpad options must be true or false.")
        if self.wispr_shortcut_mode not in {"hold_ctrl_win","toggle_ctrl_win","toggle_ctrl_win_space"}:raise ValueError("Invalid Wispr shortcut mode.")
        if not (160 <= self.camera_width <= 1920 and 120 <= self.camera_height <= 1080):
            raise ValueError("Camera dimensions outside supported range.")
        if not (256 <= self.canvas_width <= 2400 and 128 <= self.canvas_height <= 1200):
            raise ValueError("Canvas dimensions outside supported range.")
        if not (10 <= self.pinch_debounce_ms <= 500 and 0 <= self.low_score_threshold <= 1):
            raise ValueError("Invalid gesture or score settings.")
        if not (100 <= self.max_points <= 100000 and 1 <= self.max_text_characters <= 4000):
            raise ValueError("Invalid buffer limits.")


def load_config(path: Path | None = None) -> Config:
    path = path or ROOT / "config.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    local = ROOT / "config.local.json"
    if local.exists() and path == ROOT / "config.json":
        data.update(json.loads(local.read_text(encoding="utf-8")))
    allowed = {f.name for f in fields(Config)}
    if set(data) - allowed:
        raise ValueError("Unknown configuration keys: " + ", ".join(set(data) - allowed))
    return Config(**data)


def save_preferences(values):
    """Preferences only, never frames/landmarks/text; atomic local-file update."""
    local=ROOT/"config.local.json"
    current=json.loads(local.read_text(encoding="utf-8")) if local.exists() else {}
    current.update(values)
    known={f.name for f in fields(Config)}
    if set(current)-known:raise ValueError("Unknown local preference key.")
    Config(**current)
    pending=local.with_suffix(".json.tmp")
    pending.write_text(json.dumps(current,indent=2),encoding="utf-8");pending.replace(local)
