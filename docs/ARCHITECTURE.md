# SlateInk architecture and threat model

## Optional unverified gaze

The optional `gaze_allow_unverified` setting is disabled by default. The eye UI
exposes the choice as Allow unverified gaze. After a fitted nine-dot mapping, Continue
without accuracy check can skip the final five checks or continue after failure.
Desktop activation still requires Enable desktop mouse and its arming countdown.
The existing report remains failed/skipped; runtime state says accuracy unverified.

In this mode the aggregate accuracy gate, calibrated head/range rejection and
click-jitter threshold are bypassed. Fresh, finite, visible eye predictions are
clamped to the display; a deliberate pinch uses the median of recent samples.
No mapping, missing/invalid eyes, stale frames, multiple faces, ambiguous pinches,
tracking loss, camera stop, mode changes and Escape still prevent/release input.
No privacy, privilege or networking rules are changed. Turning the option off
releases input and restores the accuracy requirement. The strict-mode descriptions
below remain applicable when the override is disabled.

The default **paper/slate OCR** path reads real visible ink: bounded live camera
frame → explicitly selected homography region → in-memory snapshot/unmirror →
horizontal line extraction → pinned official local Paddle OCR ONNX model →
editable text preview → explicit acceptance → native typing. No frame histories
or exports are created. ONNX Runtime uses CUDA for balanced paper OCR when
available, with explicit actual-device labeling and a selectable CPU/required-GPU
policy. Telemetry is disabled; execution is warmed and verified before use with
automatic runtime fallback disabled. Setup uses only project-local NVIDIA wheels,
process-scoped DLL search paths and verified
local assets, and the application offline guard. Actual user writing remains a
physical accuracy gate. Complex pages and pen contact are not claimed solved.

The **hand mouse** policy is separate from stroke capture and text recognition.
Two debounced hysteretic pinches share release-to-arm and ambiguity checks.
Native left/right button ownership is recorded before pressing so even failed
press attempts can be released. Hand loss/staleness/jumps/ambiguity release holds;
mode transitions, hide/minimize, camera error and Escape disable pointer control.
Movement is now relative: joined/extended index-middle fingers engage a touchpad;
knuckle deltas pass through smoothing, a dead zone and sensitivity. Separating
fingers resets the reference, so repositioning/reacquisition does not jump.
Short pinch closure freezes movement; a sustained left pinch then permits palm
movement for dragging. WindowsMouse reads the current position and applies the
delta using normalized virtual-desktop SendInput without changing OS acceleration.
The app can control ordinary desktop mouse actions only after explicit arming;
it does not bypass UIPI/secure desktop. No event is automatically retried.

The experimental **eye gaze** path uses a pinned local MediaPipe face/iris task
only in its selected mode. Exactly one face, open visible eyes and fresh frames
produce eye-local iris ratios. Iris landmarks themselves are not screen gaze.
Nine deliberate target medians fit a regularized personal screen mapping; five
independent targets validate it, including a jitter check of the same One Euro
filter used for cursor motion, with real sample timestamps and a settling period.
At least 12 usable predictions and 75% valid coverage are required per target;
unstable pointing, stale/repeated timestamps and head drift remain blocked.
Operational failures return per-target diagnostics; selective retries replace
only failed checks and preserve the fit and other checks. No forced retry loop.
The alignment preview and all sample buffers remain local and memory-only.
Failure leaves desktop
controls disabled. Primary-monitor geometry maps onto the Windows virtual desktop.
Calibration is volatile and cleared by camera stop/restart/orientation changes.

Explicit delayed arming plus a new open pinch is required for gaze clicking.
Recent steady gaze is checked before a press; cursor movement freezes while held
to avoid unintended gaze-driven dragging. Invalid eyes, blink, head-position/
depth/pose drift, missing/ambiguous hands and stale frames release held buttons.
Face and iris observations, sample buffers and fitted weights stay in memory;
no biometric identification, storage, upload or telemetry is added. This is a
calibrated webcam prototype, not verified Vision Pro precision. Five target
checks cannot establish accuracy everywhere or across changed physical conditions.

The **pen hover pointer** tracks a selected colored marker and never infers
button states. Single-webcam contact is unvalidated. Keeping this distinction
visible prevents a guessed touch from becoming a click or a stuck drag.

Finger-letter recognition remains experimental with limited accuracy. The
earlier notes below describe retained modules, not the current default workflow.

The retained finger-letter mode is **one letter at a time**, with a square normalized canvas.
Mirror (default on) and 0/90/180/270° rotation transform camera pixels before hand
tracking. Calibration clicks, preview and landmark coordinates all use this same
oriented frame; changes invalidate calibration and current ink while preserving
collected text. No camera-coordinate correction is applied a second time.

Live recognition uses a pinned local alphabet-only MobileNetV2 ONNX classifier
(A–Z plus blank), loaded and hashed before OpenCV CPU inference. Temporal strokes
are cropped, centered with preserved aspect ratio, scaled to 96×96 and normalized
as white ink on black based on measured polarity checks. The model merges written
case; an explicit output-case control handles upper/lowercase. Top alternatives
and uncalibrated scores appear for review. Only Add letter clears its strokes and
appends an approved letter; pen lifts may separate strokes within the same letter.
Collected text has its own explicit acceptance/countdown/native typing stage.

The optional future local LLM will propose text corrections after physical letter
tests, preserve the original, and require human approval. No LLM/network endpoint
is connected now. The older TrOCR discussion below describes the first build and
the retained line-model probe, not the current live recognizer.

Target platform: Windows 11 x64 with Python 3.12 and a compatible webcam.
GPU OCR is optional and requires a supported NVIDIA GPU and driver.

The native Qt application owns visible camera controls. OpenCV DirectShow reads
the camera into a one-frame mailbox. A MediaPipe Tasks VIDEO hand landmarker runs
in a worker and publishes only the latest result. The UI validates freshness,
one-hand presence, release-to-arm, pinch hysteresis and debounce, perspective
coordinates, motion jumps, and explicit capture state before recording ink.
Stroke lists retain normalized x/y, monotonic timestamps, order and boundaries.
An adaptive One Euro filter smooths within a stroke; interruption ends the stroke.

Calibration uses TL/TR/BR/BL camera clicks and an OpenCV homography to a normalized
canvas. It is session-only and invalidated on camera restart. It assumes the
finger lies near the selected plane; a monocular camera cannot prove contact.
The image is not mirrored, avoiding a second coordinate convention.

Recognition renders only virtual ink into an in-memory monochrome line image,
then runs Microsoft's 62M-parameter TrOCR-small-handwritten locally on CPU.
The model was trained on real handwritten text lines, not finger trajectories;
synthetic ink introduces a domain gap that requires human measurement.
Alternative evaluated: PaddleOCR English mobile recognizer supports handwriting
and is smaller, but adds a separate runtime. It remains a possible benchmark
if TrOCR is the bottleneck. Printed OCR alone is unsuitable. MediaPipe provides
maintained pretrained hand landmarks; YOLO hand pose would require another
trained hand model and deployment stack. Qt provides a native Windows interface.

The recognizer's geometric mean token probability is an **uncalibrated model
score**, never a claimed likelihood that the text is correct. Every result needs
preview/edit/accept. There is no auto-commit mode. The separate Windows SendInput
adapter sends Unicode text, never shell commands or clipboard content. Linux
injection is explicitly unsupported until a session-specific safe adapter exists.
No root, administrator, security bypass, network service, or startup service.

## Trust boundaries and threats

* Camera and handwriting are private: memory-only; no video, raw-frame logs,
  trajectory logs, recognized-text logs, or implicit exports. Closing/discarding
  clears references (Python cannot promise forensic memory erasure).
* Runtime vs setup: only the explicit setup script downloads public software/model
  assets. Application startup enforces local_files_only, offline/telemetry flags,
  and a Python socket audit guard. No application networking or listeners. This
  guard is defense in depth, not an OS sandbox for malicious native libraries.
* Model supply chain: pinned Microsoft revision, restricted known asset filenames,
  SHA-256 manifests, no remote code; original PyTorch weights are loaded only with
  weights_only=True during conversion to safetensors. Runtime uses safetensors.
* Accidental strokes: capture disabled initially; calibration required; open pinch
  required before every re-arm; hand loss/two hands/stale frames/outside-region/
  implausible jumps end the stroke and require release.
* Wrong textbox: accepting arms a visible countdown. At expiry the foreground
  window must be external, stable and have a native focused control. Modified
  keys, Escape, changed focus, disappearing window, app hide/minimize, or camera
  failure cancel. SendInput checks destination repeatedly and never retries a
  partial send. Applications with elevated privilege are blocked by Windows UIPI.
  Native fixture testing found surrogate characters could reorder during a burst;
  8 ms per-character pacing preserves the measured sequence and cancellation.
  A window/control check cannot universally distinguish a textbox from a terminal;
  the human must focus an ordinary text field. Control characters including Enter
  and Tab are rejected; no command submission.
* Denial of service: one-frame buffers, maximum stroke points/text length, no
  concurrent recognition/typing requests, worker timeout/fail-closed handling.

## Primary sources reviewed

* https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python
* https://huggingface.co/microsoft/trocr-small-handwritten
* https://github.com/microsoft/unilm/tree/master/trocr
* https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_recognition.en.md
* https://github.com/ultralytics/ultralytics/blob/main/docs/en/datasets/pose/hand-keypoints.md
* https://doc.qt.io/qtforpython-6/
* https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
