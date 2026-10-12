"""Render camera-off sub-mode controls without sending input or saving preferences."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import Config,ROOT

app=QApplication([])
window=MainWindow(Config(initial_mode="hand_mouse"));window.timer.stop();window.performance_timer.stop()
window.resize(1280,900);window.show();app.processEvents()
for index,name in enumerate(("desktop","gaming","drawing")):
    window.submode_choice.setCurrentIndex(index);app.processEvents()
    path=ROOT/"artifacts"/f"ui-touchpad-{name}.png"
    window.grab().save(str(path));print(str(path))
assert window.worker is None and not window.hand_mouse.enabled
from slateink.widgets import GamingStatusOverlay
hud=GamingStatusOverlay();hud.set_status({"W","A"},"Left joystick: A + W · fist stops and recenters.")
hud.grab().save(str(ROOT/"artifacts/ui-gaming-feedback.png"));hud.close()
window.close()
