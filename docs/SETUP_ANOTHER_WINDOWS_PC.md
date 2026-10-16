# Install or update SlateInk on Windows

This guide works for a new computer and for reinstalling on your own computer.
You do not need to edit the application code. The supported desktop-input target
is **Windows 11 x64 with Python 3.12, 64-bit**, a webcam and a keyboard/mouse.
An NVIDIA GPU is optional; hand tracking runs on the CPU and paper OCR can use CPU.
Linux/macOS desktop input is not implemented in this release.

## 1. Download the source

1. Open [SlateInk_Windows_Multipurpose](https://github.com/saarthakveeraraghavan-source/SlateInk_Windows_Multipurpose).
   This repository is public; anyone can download its source ZIP without signing in.
2. Choose **Code → Download ZIP**, then **Extract all** in Windows File Explorer.
3. Put the extracted folder somewhere writable, such as Documents. Open the
   folder containing `README.md`, `run.cmd`, `slateink` and `requirements-lock.txt`.
   Do not run files inside the ZIP.
4. Right-click an empty area inside that folder and choose **Open in Terminal**.
   Use a PowerShell tab. Every command below runs from this same project folder.

Git users can instead clone the repository using their own authenticated GitHub
account. There is no need to install Git just to use the Download ZIP method.

## 2. Install Python 3.12

If `py -3.12 --version` already prints Python 3.12.x, keep your working installation
and continue to step 3. To check its architecture:

```powershell
py -3.12 -c "import struct; print(struct.calcsize('P') * 8)"
```

It must print `64`. For a new installation, use the official
[Python install manager](https://www.python.org/downloads/windows/), reopen
PowerShell and install the 3.12 runtime:

```powershell
py install 3.12
py -3.12 --version
py -3.12 -c "import struct; print(struct.calcsize('P') * 8)"
```

The manager's installation commands are documented in
[Python's Windows guide](https://docs.python.org/3/using/windows.html#installing-runtimes).
If an older Python launcher reports that `install` is not a command, open the
manager as `pymanager install 3.12` instead. Select an x64 runtime on an x64 PC;
32-bit/ARM-only environments are not this project's verified target.

## 3. Create the project environment and install dependencies

Copy one command at a time, press Enter, and wait for it to finish successfully:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

`pip check` should finish with **No broken requirements found**. Downloads can be
large: the current complete dependency set includes Torch and OCR GPU libraries
even if you will use CPU processing. Keep internet access available and allow
space for the environment, cached packages and model files. Do not install into
your global Python or change your PowerShell execution policy; these commands
use the project's environment directly and do not require activation.

## 4. Download the local models

For hand touchpad, Gaming, Drawing and air swipes, run:

```powershell
.\.venv\Scripts\python.exe scripts/setup_models.py
```

This installs the hand model plus the retained handwriting-line probe assets.
For all of the other modes, also run:

```powershell
.\.venv\Scripts\python.exe scripts/setup_alphabet.py
.\.venv\Scripts\python.exe scripts/setup_paper.py
.\.venv\Scripts\python.exe scripts/setup_eyes.py
```

These add finger-letter recognition, paper OCR and face/iris tracking respectively.
Use the full set if you want every mode available. Setup is the online step;
normal local tracking/recognition does not download models automatically. If a
download fails, rerun that setup command after restoring the connection. Wait
for its successful completion before launching the affected mode.

## 5. Start and try the app

Double-click **run.cmd**. If you want to see startup errors, use PowerShell:

```powershell
.\.venv\Scripts\python.exe -m slateink
```

Camera and desktop input start **off**. The portable repository starts in
Paper / slate OCR; choose **Hand touchpad → Touchpad: desktop** for mouse and
air-swipe controls. You can also select Hand touchpad for one launch with:

```powershell
.\.venv\Scripts\python.exe -m slateink --mode hand_mouse
```

1. Click **Start camera** and check lighting, mirror and rotation.
2. Click **Enable desktop mouse**, focus a harmless window during the countdown,
   and briefly open thumb/index and thumb/middle pinches to arm mouse input.
3. Join upright index + middle to point; index/thumb pinches click and drag;
   three extended fingers scroll. See the [gesture guide](GESTURE_GUIDE.md).
4. Show your open RIGHT hand and sweep as shown in the new named Next/Previous
   recordings. Next sweeps across your chest toward your left; Previous reverses
   toward your right. Mirror correction is automatic. No fist hold or unlock
   pose is required. Relax the fingers to return to pointing.
5. To disable this feature, **uncheck Enable window swipes**. This works while
   controls are active, cancels pending recognition and keeps mouse controls on.
   Recheck to enable it. Your choice persists for later launches.

**Escape** stops capture and releases owned input. **Ctrl+Alt+M** starts/pauses/
resumes hand touchpad while SlateInk runs. Enabled hand touchpad can keep running
when minimized with its saved background option and a visible tray/preview
indicator; use the main ×, **Stop & quit** or tray Quit to close it completely.

In every mode, check **Floating camera preview** beside the camera controls to
keep the feed above other windows. Drag its header; the position is saved. Its ×
hides that preview. In non-touchpad modes an explicitly enabled preview can keep
camera-only capture while input stops on minimize. Exclusive-fullscreen games
are not validated; try windowed/borderless mode for the desktop preview.

Only one session runs per installation. Opening the shortcut again shows the
existing window. Closing the main app waits for the isolated camera owner to
exit, including bounded cleanup of a stalled driver read.

## 6. Preferences for this computer

Camera index/exposure, speed and monitor reach can differ between computers.
For manual overrides, create `config.local.json` beside `config.json`, for example:

```json
{
  "camera_index": 0,
  "camera_exposure": null,
  "initial_mode": "hand_mouse",
  "ocr_device": "cpu",
  "touchpad_swipe_enabled": false
}
```

This example keeps the camera driver's exposure, starts in Hand touchpad, uses
CPU OCR and disables window swipes. App controls save their own preferences in
this file. Keep it valid JSON: no comments or trailing commas. Other defaults
remain in `config.json`. Choose CPU for OCR if GPU initialization is unavailable.
Hand touchpad does not require a writing-area or eye calibration.

Wispr Flow is optional and installed/configured separately. Its voice gesture starts
disabled in the portable repository. Enable it only with a matching installed
Wispr shortcut; SlateInk sends start/stop requests and does not transcribe audio.
In Desktop, show index + pinky with the thumb tucked (rock sign) to start.
Relax or remove your hand while talking, then extend index + pinky + thumb
(swag sign) with that same hand to stop and insert text. V and thumbs-up are inactive.
Eye gaze remains experimental and requires new calibration on each computer.

## 7. Update an existing installation

If you are already using this working local project, restart SlateInk to load
updated source files; do not reinstall your environment or replace your settings
to load a gesture update.

For an older Download ZIP installation:

1. Quit SlateInk completely, including its tray process.
2. Back up the old project folder, especially `config.local.json`.
3. Download/extract the latest source into a new folder using step 1.
4. Create a fresh `.venv` there using step 3. A virtual environment contains
   machine/path-specific files; do not copy it from another computer or location.
5. You may copy your old `models` folder and `config.local.json` into the new
   source folder to reuse downloaded assets and preferences. Rerun the setup
   command if an asset is missing or fails integrity checks.
6. Launch from the new folder, check camera/settings, and update any shortcut to
   point to its `run.cmd`. Keep the backup until the new copy is working.

For a Git checkout, quit the app, update your checkout without discarding local
edits, rerun the pinned dependency installation if its file changed, then restart.

## Troubleshooting

| Symptom | Next step |
|---|---|
| `py` not found | Install/reopen the Python manager, then reopen PowerShell. |
| Cannot open requirements file | Open Terminal in the extracted folder containing `requirements-lock.txt`. |
| Missing environment reported by run.cmd | Complete step 3 in that exact folder. |
| App closes immediately | Launch from PowerShell to retain the error message; confirm Python 3.12 x64 and rerun `pip check`. |
| Missing model or integrity failure | Rerun the corresponding setup script. Keep its manifest with the model files. |
| Webcam cannot open | Close other camera apps, enable Windows camera access for desktop apps, and try another `camera_index`. |
| Dark image or rejected exposure setting | Set `camera_exposure` to `null` in `config.local.json`, then restart capture. |
| GPU error during paper OCR | Select **CPU**; hand tracking itself does not need CUDA. |
| Camera LED stays on after quitting | Quit any older SlateInk copies and other camera apps. The updated build closes its camera owner; see `docs/FLOATING_CAMERA_VALIDATION.md` for checks. |
| No window switches | Check Desktop mode, enabled controls and **Enable window swipes**; keep the hand visible and release keyboard modifiers/held buttons. |
| Swipes feel too sensitive | Disable controls to reduce Swipe sensitivity or increase its cooldown, or uncheck Enable window swipes. |

Optional software verification, after dependencies are installed:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp artifacts/pytest-install-check
```

Run that command while SlateInk is closed. Optional model/public-image checks
can skip when their separate assets are absent. Portable swipe tests use bundled
synthetic fixtures. Personal reference videos/observations are local-only assets.
Native diagnostic probes send real input to disposable windows and are separate
from ordinary installation.

Source checks and recorded-gesture/native switching tests passed on the current
Windows computer. A complete dependency/model download and installation on a
second physical computer has not been verified. Physical hand/gaze accuracy and
long-session comfort depend on the camera and environment.
