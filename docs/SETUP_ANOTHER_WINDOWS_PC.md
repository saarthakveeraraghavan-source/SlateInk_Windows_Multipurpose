# Set up SlateInk on another Windows computer

You usually do not need to change the application code. Install the environment
and model assets on the new computer, then adjust its camera and input settings.
This project targets **Windows 11 x64 with Python 3.12, 64-bit**.
A compatible webcam is required for camera-based modes. An NVIDIA GPU is
optional for paper OCR; CPU operation is available.

## 1. Download and extract the project

1. Sign in to GitHub with an account that has access to this private repository.
2. On the repository page, choose **Code → Download ZIP**.
3. Extract the ZIP into a writable folder. Work inside the extracted folder that
   contains `README.md`, `run.cmd` and `requirements-lock.txt`.
4. Install Python **3.12, 64-bit**, including the Windows Python launcher.
5. Open PowerShell in that project folder. Check the Python version:

```powershell
py -3.12 --version
```

It should report Python 3.12.x. If `py` is not recognized, check that the Python
launcher is installed, then reopen the terminal.

## 2. Install dependencies and models once

Run these commands in order from the extracted project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/setup_models.py
.\.venv\Scripts\python.exe scripts/setup_alphabet.py
.\.venv\Scripts\python.exe scripts/setup_paper.py
.\.venv\Scripts\python.exe scripts/setup_eyes.py
```

Wait for each command to finish successfully before running the next.
Internet access is needed for these downloads. The setup commands recreate the
local Python environment and download public models omitted from GitHub.
The dependency list includes GPU libraries even when you plan to use CPU OCR.
The commands use the environment directly; PowerShell activation is unnecessary.

The model scripts provide hand tracking and the retained line-model probe
(`setup_models.py`), experimental finger-letter recognition
(`setup_alphabet.py`), paper/slate OCR (`setup_paper.py`), and experimental
face/eye tracking (`setup_eyes.py`).

## 3. Launch the application

Double-click **run.cmd**, or run:

```powershell
.\.venv\Scripts\python.exe -m slateink
```

Camera and desktop input start off. Choose your mode, start the visible camera
preview, and explicitly enable the applicable controls.

The repository starts in **Paper / slate OCR**. Choose **Hand touchpad** for
Desktop, Gaming or Drawing tablet. To select Hand touchpad for a single launch:

```powershell
.\.venv\Scripts\python.exe -m slateink --mode hand_mouse
```

## 4. Adjust settings for this computer

| Setting | What to check or change |
|---|---|
| Webcam | If the wrong camera opens, change `camera_index` in configuration. Check mirror and rotation in the app. |
| Exposure | If the preview is dark or the webcam behaves poorly with fixed exposure, set `camera_exposure` to `null` to use the webcam driver's default. |
| OCR processing | Select **CPU** for a computer without a compatible NVIDIA GPU. **GPU when available** tries GPU and labels CPU fallback; **GPU required** fails when CUDA cannot run. |
| Pointer and drawing speed | Adjust to the new webcam placement, field of view and monitor. Desktop and drawing speeds are separate. |
| Gaming travel | Adjust the joystick travel to a comfortable left-palm movement. Physical right hand controls the mouse; physical left hand controls WASD. |
| Starting mode | `initial_mode` can be `paper`, `hand_mouse`, `pen_pointer`, `finger_letters` or `eye_gaze`. |
| Wispr Flow | Install and configure Wispr separately. Enable SlateInk's optional V gesture and select a shortcut matching Wispr. The default binding is Ctrl+Win toggle; the gesture starts disabled. |
| Calibration | Calibrate eyes or the writing/pointer area on this computer when using those modes. Hand touchpad needs no area calibration. |

Settings available in the app are saved as local preferences. For manual
overrides, create or edit `config.local.json` in the project folder; it is ignored
by Git. Include only settings you want to override, for example:

```json
{
  "camera_index": 0,
  "camera_exposure": null,
  "initial_mode": "hand_mouse",
  "ocr_device": "cpu"
}
```

Change the camera index only if necessary. Keep the file valid JSON: no comments
or trailing commas. `config.json` supplies the remaining defaults.

Personal preferences do not transfer automatically. Eye calibration stays in
memory and must be repeated after stopping/restarting the camera or changing its
position. Unverified gaze control is disabled in the repository defaults.

## 5. First-use check and troubleshooting

- Start with a disposable document or harmless test window. Test pointing,
  clicks, dragging, scrolling and the chosen mode's gestures.
- **Escape** stops capture and releases owned input. **Ctrl+Alt+M** controls
  hand-touchpad start/pause/resume while SlateInk runs.
- If `run.cmd` reports a missing environment, complete step 2.
- If the camera cannot open, close other camera apps, check Windows camera
  access for desktop apps, and try another camera index.
- If a model is missing, rerun the corresponding model setup script.
- If GPU OCR fails, select **CPU** and try again.
- If the app closes with an error, launch it from PowerShell with the command in
  step 3 so the error remains visible.
- Read the [gesture guide](GESTURE_GUIDE.md) for detailed input instructions.

Optional software checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Some integration checks skip when local models or public image fixtures are
absent. Public test images and machine-specific reports are not bundled.
Software checks do not establish physical hand/gaze accuracy, handwriting
quality, game compatibility or actual Wispr acceptance.

The repository copy passed software checks on the original Windows computer.
**A clean installation on a second computer has not yet been validated.**
