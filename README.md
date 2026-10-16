# SlateInk for Windows — multiple modes and input methods

SlateInk is a local webcam writing and desktop input application for **Windows 11 x64**.
It offers several modes and ways to use your hands, eyes, pen, and paper.
Physical accuracy and long-session reliability remain experimental.

## Modes and input methods

| Mode | Input method and actions |
|---|---|
| Paper / slate OCR | Capture real ink from a selected webcam region, recognize locally, review/edit, then explicitly type accepted text |
| Hand touchpad — Desktop | Joined index/middle fingers move the cursor; pinches click, double-click, drag and select; three fingers scroll; helper palm enables precision; optional natural air swipes change windows |
| Hand touchpad — Gaming | Physical left palm operates a centered WASD joystick; physical right hand moves and clicks the mouse |
| Hand touchpad — Drawing tablet | Index-only drawing, index/middle hover and pen lift, pinch tool clicks; optional left-hand clicks with right-hand drawing |
| Eye gaze + pinch | Experimental nine-target eye calibration and five-target accuracy check, followed by gaze pointing and pinch clicks |
| Pen hover pointer | Experimental colored-marker tracking for pointer movement; pen contact does not infer a click |
| Finger letters | Experimental one-letter-at-a-time virtual handwriting, local recognition, review and explicit acceptance |
| Optional Wispr Flow shortcut | Rock sign (index + pinky, thumb tucked) starts; swag sign (index + pinky + thumb) with the same hand stops dictation through a matching installed Wispr shortcut; disabled by default |

See the [gesture guide](docs/GESTURE_GUIDE.md) or its [HTML version](docs/GESTURE_GUIDE.html)
for Desktop, Gaming, Drawing, background use, scrolling, shortcuts and pause/stop gestures.

## Install and run on Windows

Start with the [installation and update guide](docs/SETUP_ANOTHER_WINDOWS_PC.md).
It explains Download ZIP, Python 3.12 x64, dependencies, models, first use,
updates, saved preferences and troubleshooting. This public repository can be
downloaded without signing in.

**Installing on another computer?** Follow the [step-by-step Windows setup guide](docs/SETUP_ANOTHER_WINDOWS_PC.md), including camera, CPU/GPU, mode, Wispr and calibration settings.

Use Python **3.12 x64**, Windows 11, and a compatible webcam. Dependencies are pinned.
An NVIDIA GPU is optional for paper OCR; CPU operation is available.
The model setup scripts download public model assets and verify their hashes.
Run installation commands from the repository folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/setup_models.py
.\.venv\Scripts\python.exe scripts/setup_alphabet.py
.\.venv\Scripts\python.exe scripts/setup_paper.py
.\.venv\Scripts\python.exe scripts/setup_eyes.py
.\.venv\Scripts\python.exe -m slateink
```

After installation, double-click **run.cmd**. Camera and desktop input start off.
Choose a mode, start the visible camera preview, and enable its controls explicitly.
`--camera` starts a visible preview with input paused; `--mode hand_mouse` selects
Hand touchpad for that session. **Escape** stops capture and releases owned input.
**Ctrl+Alt+M** starts/pauses/resumes the hand touchpad while SlateInk runs.
Gaming uses right-hand mouse / left-hand WASD roles. Drawing starts with index/middle
hover, then folding only the middle finger begins index drawing.

## Configuration

### Latest camera and Wispr controls

- **Floating camera preview:** optional small feed above desktop windows in all
  modes. Drag its header to place it; position and on/off choice save locally.
- **Close / minimize:** closing exits and releases the camera. Minimizing follows
  the saved background setting; the preview can remain above other apps.
- **Click:** index/thumb contact and release clicks; two cycles double-click.
  An idle open palm arms clicks even when swipes are enabled.
- **Wispr:** enable **Rock starts / swag stops Wispr** in Desktop. Raise index
  and pinky, fold middle/ring and tuck the thumb to start. Relax or lower your
  hand while talking. Extend index + pinky + thumb with that SAME hand to stop.
  V and thumbs-up are inactive. Match the shortcut dropdown to Wispr's own
  start/stop setting. Escape cancels.

### Turn window swipes off or on

In **Hand touchpad → Touchpad: desktop**, uncheck **Enable window swipes**.
You can do this while mouse controls are active: it cancels a pending swipe,
keeps the mouse enabled and saves the choice for later launches. Recheck to
enable swipes. For a manual override, put `"touchpad_swipe_enabled": false` in
`config.local.json`. Use an open RIGHT hand and sweep across your chest for next; reverse for
previous. Mirroring is corrected automatically. Swipes are inactive in Gaming and Drawing. Disable controls
before changing swipe sensitivity or cooldown.

`config.json` contains portable defaults from the configuration class. Paper OCR
is the initial mode; unverified gaze and Wispr gestures are disabled by default.
Personal overrides and preferences belong in ignored `config.local.json`.
Adjust camera index, exposure, mirror/rotation, pointer and drawing speeds,
gaming travel, scrolling and OCR device through the app or configuration.
Set `camera_exposure` to `null` to retain the webcam driver's exposure default.

## Privacy and desktop input

Normal recognition and tracking use local models. Camera frames, strokes,
recognized text and eye calibration remain in memory; no recording history is
created automatically. Runtime disables telemetry and rejects Python socket
connections; this guard is not an OS sandbox for native dependencies.
Model installation requires network access. Optional Wispr Flow uses its own
microphone, transcription and privacy settings; SlateInk requests shortcuts.
Windows input injection runs at ordinary privilege and does not bypass Windows
protections. Review recognized text before accepting it into a destination.
When background touchpad operation is enabled, a visible tray indicator remains.

## Checks and limitations

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp artifacts/pytest-install-check
```

Tests cover gesture transitions, geometry, input ownership/release, focus loss,
camera interruption, modes, configuration, privacy and UI behavior. Model and
public-image integration checks need optional local assets; absent assets should
skip those checks. Portable swipe tests include independently generated synthetic hand fixtures; original personal recordings and machine-specific
reports are excluded. Setup scripts obtain models; probes expecting images in
`artifacts/` require separately supplied public fixtures. Create `artifacts/`
before running probes that write reports. Native probes send real desktop input
to disposable test windows and should be run deliberately.

Software checks do not establish physical hand/gaze accuracy, pressure/tilt,
handwriting quality, game compatibility or actual Wispr acceptance.
See the [evaluation procedure](docs/EVALUATION.md) and [architecture](docs/ARCHITECTURE.md).
Linux desktop input is unavailable; no Linux compatibility is claimed.
The proposed local LLM correction stage is not implemented.

## Repository contents

- `slateink/`: application source and Windows input adapters.
- `scripts/`: public model installers and diagnostic/native probes.
- `tests/`: automated checks.
- `docs/`: general architecture, evaluation procedure and gesture guides.
- Dependency pins, launcher and portable configuration.

Personal configuration, evaluation results, logs, captures, original recordings,
generated artifacts, downloaded models, desktop shortcuts and the local Python
environment are excluded. Hardware-specific reports and personal trial history
are excluded from the documentation copy. Local workspace files are unchanged.

