# Human evaluation: required before any reliability claim or air mode

Unverified eye control is optional and disabled by default. Allow unverified gaze permits
activation with a fitted nine-dot mapping even when the last five accuracy checks
fail or are skipped. Use Continue without accuracy check, then Enable desktop
mouse; check the accuracy-unverified status. Test pointing and left/right pinch
clicks in an ordinary disposable window. Confirm Escape, camera stop, missing
eyes, stale frames and ambiguous gestures release input. Turning the option off
must restore the strict accuracy gate. Earlier mandatory-gate statements below
describe strict mode; neither mode establishes physical accuracy without testing.

## Current physical checkpoint: paper OCR, then hand mouse

Finger-letter recognition has limited accuracy. That mode is experimental.
The repository default is **Paper / slate OCR**, with actual-ink recognition.

1. In Paper/slate OCR, start the camera and ensure the writing is upright.
   Select a rectangular area around one or two lines, clockwise from top left.
2. Write `Hello world` in large real ink on paper/slate. Remove hand and pen.
   Click Capture writing & recognize. Check whether the text matches; correct it
   in the preview before Type collected text. Focus a harmless test textbox.
3. Try several words/sentences from the existing matrix, both cases, repeated
   letters and punctuation. Record actual word/character errors; the two public/
   synthetic fixture successes do not establish user accuracy. Test dark-slate
   inversion if applicable and record lighting/angle/letter-size conditions.
4. Choose Hand touchpad; no area calibration; enable control (3-second delay).
   Show one hand and open both thumb/index and thumb/middle pinches. First verify
   relative cursor movement with joined/extended index-middle fingers. Separating
   them must allow hand repositioning without a cursor jump. Test stationary
   jitter, Speed adjustment, then left click, held left dragging and release in a
   harmless test window. Test middle/thumb right click separately. If simultaneous
   pinch detection interferes, disable its right-click checkbox and record it.
5. Verify Escape, hand disappearance, two hands, leaving the camera view, changed mode,
   camera stop, hide/minimize all release holds. Never test gestures first over
   controls that delete data or confirm irreversible actions.
6. Optional pen-hover trial: place a bright colored marker near the pen tip,
   select it, calibrate, enable hover pointer. Check position/loss/ambiguous-color
   behavior. No pen-touch click/drag is enabled; do not count that requirement as
   passing. The confirmed webcam-only hardware has no validated contact signal.

## Experimental webcam gaze checkpoint

Aim the webcam at your face and choose Eye gaze + pinch. Keep your head/webcam
stationary in good light, with both eyes clearly visible. Start camera and run
Calibrate eyes & check accuracy: align your face in the local preview and click
Start calibration. Look steadily at nine dots while their rings fill and advance
automatically, followed by five different validation dots. Manual Space capture
is optional. Enter returns. If one check fails, it must finish with a reason and
offer Retry failed dots only; successful checks and the nine-point fit stay intact.
Test early Space, blink/dropouts and stale/duplicate frame timestamps: these must
not erase all progress, manufacture samples, or cause a silent five-dot loop.
Verify genuinely unstable/missing pointing data still blocks desktop input.
Failed/unstable calibration must keep the Enable desktop mouse button blocked.
Never count a synthetic calibration fixture as physical success.

After a pass, explicitly enable control in a harmless test window. Test large
targets first, then record misses on smaller targets across the screen. Open
both pinches before clicking. Thumb/index should left-click at steady gaze;
thumb/middle should right-click. Cursor must freeze during a held pinch. Blink,
move/turn your head, cover eyes, show another face/hand, stop camera and press
Escape: verify controls pause/release and clicks cannot occur while invalid.
Recalibrate after restarting or moving the camera. Record failure conditions
locally only if you opt in; no images, eye samples or user text are saved by the
application. Calibration passing is a limited check, not a global accuracy claim.

The earlier finger-letter protocol below is retained for comparison only.

No accuracy percentage is claimed. Automated safety/geometry tests and a public
handwriting model smoke test do not validate this user's finger writing.

## First physical test (stable checkpoint)

1. Put a flat slate or blank sheet under the webcam in good light. Point the camera
   down toward the surface. Keep the entire hand visible, not just the fingertip.
2. Start camera. Confirm the visible CAMERA ACTIVE indicator and live FPS.
3. Check mirror/rotation: rightward physical movement should feel rightward on
   screen. Choose Calibrate slate and click a **roughly square** letter area:
   top left, top right, bottom right, bottom left in the displayed view.
4. Enable writing. Show one hand and separate thumb/index for at least 0.1 seconds.
   Pinch gently, move along a horizontal line, then release. Repeat vertically.
5. Expected: teal index marker follows the fingertip; virtual ink appears only
   while pinched; separate motions form separate strokes. Paused movement adds no
   ink. Hand loss and leaving the region lift the pen and require reopening pinch.
6. Clear. Write A, recognize, review/edit, then Add letter & next. Write O over
   the **same physical area** and repeat; collected text should read `ao` with
   default lowercase output. Test `hello` one letter at a time, including repeat
   letters. Add space between words. Click Type collected text and click a harmless
   Notepad textbox, keep focus there and release modifier keys. No Enter is sent.

Pinching changes fingertip posture and may conceal landmarks against the surface.
If this prevents reliable motion, record the failure; compare a deliberate
non-writing-hand gesture or explicit held key in a later iteration. Do not label
the pinch scheme reliable until tested. A single webcam does not measure touch.

## Test matrix

Run each case at least three times at baseline. Submit one letter at a time;
assemble the words/sentences in the collected-text field.
Then repeat representative cases under changed lighting/angle/speed. Keep rows
for failures as well as successes. Use `evaluation-results.csv` (empty initially).
Raw frames, trajectories, recognized text and user ground truth are not saved
automatically. If you elect to save these, explicitly opt in and keep them local.

| Group | Cases |
|---|---|
| Letters | a, e, i, m, n, r, s, t; A, B, H, M; isolated dots/crossbars |
| Short words | hello, ink, cat, book, letter, coffee |
| Long words | handwriting, differentiate, acceleration |
| Sentences | Hello world. / Differentiate velocity. / The little book is good. |
| Case/spaces | Hello World / HELLO WORLD / hello world; wide/narrow word gaps |
| Repeated letters | little, letter, coffee, book |
| Digits/punctuation (exploratory) | 0123456789; 12.5, hello!; 42? |
| Fast/slow | ordinary baseline; deliberately fast; deliberately slow |
| Camera angle | baseline; slight left/right tilt; recalibrate after camera moves |
| Lighting | bright diffuse; ordinary room; mild shadow; avoid darkness |
| Fail-safe | hand disappears; two hands; outside slate; minimize; Escape |
| Input | plain Notepad; browser textbox; capitalization, spaces, punctuation |
| Input failure | focus left in SlateInk; switch focus during send; held Ctrl; Escape |

## Record failures by pipeline stage

* **Tracking**: fingertip missed, swapped hand, jitter, jump, occlusion, stale frame.
* **Gesture segmentation**: false pinch, missed pinch, accidental pen-down, pen
  sticking down after release. Compare visible ratio with configured thresholds.
* **Stroke segmentation**: unwanted connecting line, lost crossbar/dot, line cut
  at boundary, fast movement rejected. Inspect visible ink before recognition.
* **Recognition**: ink looks correct but text differs. Log CER/WER in aggregate;
  identify isolated letters, repeats, spaces, case and punctuation separately.
* **Text injection**: correct preview but missing/duplicated/wrong destination
  characters, blocked input, cancellation. Never automatically resend failures.

Capture duration, camera/tracker FPS, tracking median/p95 latency, recognition
latency, process CPU/RAM. Compute CER = character edit distance / ground-truth
characters, WER similarly by words, plus exact-line rate. Report sample counts
and test conditions. Token probability is not recognition accuracy. Choose the
largest measured bottleneck before tuning; do not optimize the demo by deleting
failed rows. Air mode remains gated on reliable end-to-end slate measurements.
