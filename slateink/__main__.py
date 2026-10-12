import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
from .privacy import enforce_offline


def main():
    parser = argparse.ArgumentParser(description="Local paper writing, hand touchpad and experimental gaze; camera off until requested.")
    parser.add_argument("--camera", action="store_true", help="Start visible camera, with writing still paused.")
    parser.add_argument("--mode",choices=("paper","hand_mouse","pen_pointer","finger_letters","eye_gaze"),help="Select a mode for this launch without changing saved defaults.")
    args = parser.parse_args()
    enforce_offline()
    from .config import ROOT
    (ROOT/"logs").mkdir(exist_ok=True)
    handlers=[RotatingFileHandler(ROOT/"logs"/"application.log",maxBytes=500000,backupCount=2,encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",handlers=handlers)
    # Third-party verbose model logging is unnecessary during normal use.
    logging.getLogger("transformers").setLevel(logging.ERROR)
    from .app import run
    return run(args.camera,args.mode)


if __name__ == "__main__":
    sys.exit(main())
