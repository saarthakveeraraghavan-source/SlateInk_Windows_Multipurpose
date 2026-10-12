"""Render native camera-off layout; no private camera content in screenshots."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from slateink.app import MainWindow

app=QApplication([])
window=MainWindow()
window.show()

def finish():
    print("Available font families:",len(QFontDatabase.families()))
    path=Path(__file__).resolve().parent.parent/"artifacts"/"ui-camera-off-native.png"
    window.grab().save(str(path))
    for index,name in ((1,"hand-touchpad"),(4,"eye-gaze")):
        window.mode_choice.setCurrentIndex(index);app.processEvents()
        window.grab().save(str(path.with_name(f"ui-{name}-camera-off.png")))
    print("Camera-off UI rendered. No camera opened.")
    window.close()

QTimer.singleShot(1500,finish)
app.exec()
