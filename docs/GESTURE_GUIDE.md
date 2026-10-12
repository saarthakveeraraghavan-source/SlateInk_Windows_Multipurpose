# SlateInk hand touchpad guide

Select Hand touchpad to use these gestures. Camera starts **off**. Hand tracking
stays on this computer; Wispr Flow handles its own microphone, transcription and
insertion under your existing Wispr settings.

## Start in one minute

1. Open **run.cmd**. Choose **Hand touchpad** if another mode is selected.
2. Point the webcam toward your hands. Use front lighting and leave room around
   your fingers and knuckles. Mirror camera is on by default. No writing-area or
   eye calibration is needed for this mode.
3. Choose **Control hand: first shown**, or explicitly choose left/right. When
   using first shown, show only the hand you want to control the pointer first.
   Its role stays locked until you disable and re-enable control. The other hand
   becomes the helper. The preview labels show the current roles.
4. Click **Start camera**, then **Enable desktop mouse**. Wait three seconds and
   briefly open thumb/index and thumb/middle pinches to arm. Join and extend index
   and middle fingers, keeping ring and little finger curled, then move your hand.
5. Alternatively, **Ctrl+Alt+M** starts camera and arms the hand touchpad from
   another app. Once enabled, that shortcut pauses/resumes the controls.

## Gesture reference

| Action | Gesture | What happens |
|---|---|---|
| Move cursor | Control hand: index + middle straight and close together; ring/little finger curled | Relative movement from the current cursor, with smoothing and a dead zone |
| Reposition hand | Separate index/middle or relax them | Cursor pauses; joining again does not jump to a camera position |
| Left click | Thumb + index pinch, then release; keep another finger extended | Click stays at the target instead of drifting with pinch closure |
| Double click / select a word | Two quick index/thumb pinch-and-release cycles | Normal Windows double click; word selection depends on the destination app |
| Select text / drag a window | Hold index/thumb pinch, then deliberately move the whole hand | Left button stays down. A settling interval and movement threshold prevent tiny motion from becoming a drag. Release to drop/finish |
| Right click | Thumb + middle pinch, then release; keep another finger extended | Normal right click. Separate index/middle enough for the thumb to clearly target one finger |
| Vertical scroll | Control hand: index + middle + ring extended, little finger curled, thumb away; move up/down | Up moves toward earlier content; down toward later content. Reverse scrolling flips this |
| Horizontal scroll | Same three-finger pose; move sideways first | Scrolls sideways in apps that support it. Lower the ring finger to end scrolling and choose a new axis |
| Precision pointing | Helper hand: open palm, all four fingers extended and thumb away | Slower, finer pointer movement while the control hand points or selects |
| Next window | Sweep the relaxed control hand sideways toward the center, as in the latest Next_Swipe-Gesture.mp4 | One next-window switch. No open palm needed. Desktop only |
| Previous window | Sweep in the opposite direction, as in the latest Previous_Swipe-Gesture.mp4 | One previous-window switch. Fingers can stay relaxed. Desktop only |
| Pause / resume | Both hands: open palms held for about one second | Toggles pause. Lower/relax the pose before showing it again. Camera keeps running so resuming is possible |
| Start Wispr Flow | Either hand: V sign, index/middle straight and spread apart, ring/little finger curled; hold steadily about 0.7 seconds | Sends your configured Ctrl+Win start shortcut once. Pointing and clicking freeze during dictation |
| Finish Wispr and insert text | Lower the V sign, relax those fingers, or remove that hand | After a short grace period, sends Ctrl+Win once more. Wispr performs transcription and insertion |
| Start/pause/resume by keyboard | Ctrl+Alt+M while SlateInk is running | Global shortcut; no need to focus the SlateInk window |
| Emergency stop / cancel voice | Escape or Stop everything | Stops camera, releases app-owned mouse buttons and keys, and cancels an active Wispr gesture |

Keep another finger extended while pinching: a relaxed closed fist is deliberately
excluded from clicking. Clicks require opening the pinches after enabling or
interrupted tracking. An ambiguous thumb touch between two fingertips does not click.

## Swipe to change windows

In **Touchpad: desktop**, use the natural sideways air strokes in your **latest**
two recordings. Keep your fingers relaxed; you do not have to open your palm,
straighten every finger, or deliberately turn the wrist between two poses.

- **Next window:** sweep toward the center as shown in **Next_Swipe-Gesture.mp4**.
- **Previous window:** sweep back the other way as shown in
  **Previous_Swipe-Gesture.mp4**.

Let the hand settle momentarily between strokes. Recognition arms automatically
in about 0.1 seconds and follows the sideways motion. A folded hand can also
swipe. Stationary hands and vertical arm movements do not change windows.
Each stroke switches once, followed by the adjustable **0.8-second cooldown**.
There is no required finish-pose hold or palm-opening step. Mirroring preserves
the actions demonstrated in the videos.

Pointing and clicks pause while the sideways swipe gesture is reserved. Return
to the usual upright, joined index + middle pointing pose to resume the mouse.
Normal pointing and three-finger scrolling keep their existing gestures.
Two open palms still pause. An upright V still controls Wispr; a transient V-like
estimate during an air stroke cannot start dictation, and a helper V or active
dictation retains priority.

Eligible open windows cycle in a stable order, including minimized windows;
changing the focused window does not reorder the cycle. New windows join the
end and closed windows leave it. SlateInk, desktop/taskbar, tool windows,
disabled windows and windows hidden on another virtual desktop are excluded.
This changes the focused window; it does not launch apps or change workspaces.

Uncheck **Enable window swipes** to disable every next/previous air swipe.
You can do this while mouse controls are active; a pending swipe is cancelled
and mouse control stays enabled. The choice saves locally and survives restart.
Recheck it to turn swiping back on. Disable controls before changing **Swipe
sensitivity ×** (higher needs less sideways travel) or **Swipe cooldown**.
Window switching is inactive in Gaming and Drawing.

Tracking safety, two-palm pause, active dictation and helper Wispr gestures take
priority. Swipes cannot interrupt an owned click/drag, a physical mouse button
or a held keyboard modifier. One brief missed tracking frame during an active
stroke can be bridged for up to 160 ms while pointer input is frozen. Switching
still requires real, confirmed hand observations. Longer loss, stale frames,
confidently ambiguous hand roles and large wrist jumps cancel the stroke.
Low-confidence duplicate estimates are ignored. First-shown hand selection
settles briefly at startup rather than permanently locking a single wrong label.

Windows foreground restrictions still apply. The switch uses a brief owned Alt
press and the standard foreground API, releases Alt immediately, and stops hand
control if Windows does not confirm activation. No system focus settings change.
The activation rules are documented by Microsoft in
[SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)
and [LockSetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-locksetforegroundwindow).

Validation on 12 October 2026 replayed both latest supplied recordings through the real
local tracker and full Desktop session, with exactly one correctly named switch
and zero mouse/voice events in each recording, mirrored and unmirrored. Recorded
hand observations also drove actual native focus changes among three disposable
Windows windows with ordinary permissions. The probe verified stable cycling,
minimized-window restoration, window filtering, Alt release and fixture cleanup.
All 339 regression tests passed. No live camera was opened; a fresh live-hand
trial and long-session comfort remain untested.

## Gaming sub-mode

Choose **Hand touchpad → Touchpad: gaming**, then Start camera and Enable gaming
controls. Focus your game during the three-second countdown. Right hand retains
the existing movement and left/right pinch clicks. Show both hands; the roles
are fixed, so the Control hand setting is hidden in this sub-mode.

Hold your **left** palm still for about 0.3 seconds at a comfortable center,
with at least three fingers extended. No preliminary fist is needed. Move that
palm as a small joystick:

| Left palm movement | Held keys |
|---|---|
| Forward | W |
| Left | A |
| Back | S |
| Right | D |
| Diagonal | Corresponding pair, such as W + A |
| Return to center | Release movement keys |
| Close fist | Release immediately; reopening sets a new center |

This position-based design avoids memorizing four finger shapes and supports
diagonals. It is an implementation choice awaiting your comfort/recognition
trial, not a measured optimal gesture. **Joystick travel × palm** controls the
distance needed: increase it if motion engages too easily, lower it if travel
feels tiring. A short press debounce and wider release zone limit key chatter.
Wispr is inactive here. Loss of the left hand releases WASD; loss of the right
hand, ambiguous roles, stale tracking or changing focused windows releases all
input. Hold a steady palm again after interrupted tracking to set a new center.
One/two extended fingers stop keys without discarding an established center;
a fist stops and clears the center. Ctrl+Alt+M pauses/resumes gaming. The
two-open-palms pause gesture is inactive here because it conflicts with steering
while the right mouse fingers are extended.

**Show WASD status over other apps** displays held keys, centering progress and
tracking/focus messages over Blender or your game. It does not accept clicks or
keyboard focus. The display hides when gaming input stops. Your current
**Joystick travel × palm** preference may require a noticeable sweep; lowering
the value reduces travel. Start with 0.22 if 0.60 feels too large.

Ordinary Windows scan-code input is used; some games may not accept it. The
right mouse keeps the existing desktop movement policy; game camera-look
compatibility varies by application. The complete joystick path has passed an
actual Blender 5.2.1 Walk Navigation test in a separate factory scene using
synthetic hand observations. This proves native key acceptance in that mode,
not physical recognition of your hand. No anti-cheat bypass is attempted.

## Drawing tablet sub-mode

Choose **Hand touchpad → Touchpad: drawing tablet**. Select a brush/pen with
your physical mouse in Paint, Xournal++ or another drawing app. Start camera,
enable drawing controls and focus that app during the countdown.

| Control hand gesture | Effect |
|---|---|
| Index + middle extended, ring/little curled | Hover without ink; hold briefly to arm |
| Index only extended | Hold left mouse and draw with the moving index tip |
| Thumb + index pinch/release; keep middle extended | Left click a tool at the hover cursor; cursor freezes through the pinch |
| Raise middle finger again | Lift the pen immediately and hover |
| Fold fingers / relax hand | Lift and reposition; cursor remains where you left it |
| Tracking interruption or window change | Lift pen and require index + middle to re-arm |

You do not need to pinch to draw. For tool selection, hover to the target with
index + middle, then pinch thumb/index and release while middle stays extended.
After clicking, return to index + middle hover before starting another stroke;
releasing a click into index-only does not resume ink accidentally.
Keep the index finger visible and comfortably extended, with thumb away for ink;
avoid changing its position abruptly while folding/raising the middle finger.
The pen settles for about 60 ms on stroke start. **Drawing speed ×** adjusts
reach with a constant gain: the same camera-pixel distance maps to the same
screen-pixel distance horizontally, vertically and diagonally. Camera aspect
is corrected before smoothing. The desktop touchpad speed/acceleration policy
is unchanged. Drawing mode has no scrolling, right pinch click or Wispr gesture.

Two open palms or Ctrl+Alt+M pause/resume. Escape stops camera and lifts the pen.
Try a cross, circle and square, then several disconnected short strokes.
Check comfort, jitter, pen lifts and app compatibility with your real hand.
This is webcam mouse drawing: pressure and pen tilt are unavailable, and
physical precision has not been validated as a dedicated tablet replacement.

**Left hand clicks / right hand draws** is optional and off by default. When
checked before enabling controls, the physical right hand always supplies
cursor/ink movement, and the left thumb/index pinch supplies tool clicks.
Keep another left finger extended when pinching. Open the left pinch briefly to
arm it. A helper click lifts any ink and freezes the cursor through the click;
show right index + middle to return to hover. The left hand's position never
changes the drawing filter, scale or coordinates. Turning the option off
restores the existing single-hand workflow.

## Wispr Flow with your configuration

Your confirmed configuration is **Ctrl+Win: press once to start, press again to
stop**. SlateInk's dropdown is set to that behavior; it does not change Wispr's
settings. Wispr Flow must already be running, signed in and working normally.

1. Focus an ordinary textbox so its caret is visible. Release keyboard modifiers.
2. Use a steady V sign with the helper hand, or the control hand if using one hand.
   Start from a neutral hand pose; an already-held V at activation does not start
   dictation. Keep only the two intended fingers extended and separated.
3. Wait for **Wispr's own ping/recording indicator**, then speak. SlateInk's
   status confirms the gesture/shortcut request, not that Wispr accepted it.
4. Lower the V sign and wait for Wispr to insert your words. Brief tracking
   dropouts have a grace period. Do not press the physical Wispr toggle while
   the hand-controlled session is active, as that can desynchronize the toggles.
5. Open the pinches again to resume pointing. Changing the focused window/control,
   stopping capture, pausing controls, camera staleness or Escape cancels the
   hand-controlled voice session instead of sending another start/stop toggle.

The **V gesture → Wispr Flow** checkbox disables the voice gesture if you do not
want it. Other supported bindings are standard Ctrl+Win hold-to-talk and
Ctrl+Win+Space start/stop; select one only when it matches your Wispr settings.
Wispr owns the transcript and clipboard behavior. SlateInk does not read, save,
upload or paste the spoken text itself, and never adds Enter or message submission.

## Daily-use settings and background use

- **Speed** controls pointer reach. Start at 1.00; lower it for fine targeting.
  Small movements already use a lower gain than larger sweeps.
- **Scroll** controls how much a three-finger sweep scrolls. Start at 24; lower
  it if pages move too quickly. **Reverse scrolling** changes the direction.
- Disable desktop control before changing gesture/hand/scroll/Wispr settings.
  These preferences are saved locally for later launches; no calibration or
  camera/voice history is saved with them.
- **Keep running when minimized** lets an enabled hand touchpad continue while
  the main window is minimized. The system-tray cursor icon shows camera/control
  status. Its menu can pause/resume, show SlateInk, stop the camera, or quit.
- Pause keeps the camera on and monitors the resume gesture. **Escape**, the tray
  Stop camera action and **Stop & quit** release capture and app-owned inputs.
- Background capture is allowed only for the enabled hand touchpad with a visible
  tray indicator. Other modes retain their stop-on-hide/minimize behavior. If the
  system tray is unavailable, keep the main window visible.
- Ctrl+Alt+M is registered only while SlateInk runs. If another application owns
  it, SlateInk reports the conflict and keeps its buttons/gestures available.
  There is no startup service, automatic login launch or administrator requirement.

## The lower-edge / outside-area problem

Hand touchpad has **no calibrated writing region**. The previous boundary check
also required the inferred wrist and palm edge to stay inside the image. It now
allows those joints a little beyond the camera edge when the control fingertips
and knuckles remain visible. A regression check covers this lower-edge case.

Keep thumb, index/middle fingertips and the two main knuckles visible. If those
actually leave the frame, tracking pauses and buttons release. Aim the camera a
little lower/farther back if you run out of hand room. If the message mentions a
calibrated **slate/writing area**, check the mode: that restriction belongs to
Finger letters or paper/pen workflows, not the hand touchpad.

## First real-use check

Use a disposable document first. Move and stop on a small target, click it,
double-click a word, drag-select a sentence, right-click, and scroll both axes.
Test helper precision, two-palm pause/resume, Ctrl+Alt+M and Escape. Then focus a
blank textbox and dictate one short sentence using the V gesture. Confirm
Wispr's recording indicator, the stop action and insertion in that same field.

Native mouse tests have verified clicks, dragging, window dragging, scrolling,
relative movement and double-click word selection. Native keyboard delivery and
the global hotkey were tested in a disposable receiver with substitute keys,
without activating Wispr or recording audio. Minimize/pause/resume and gesture
policies were tested with synthetic hands. **Actual Wispr acceptance, physical
gesture comfort and long-session daily reliability still need your real-use trial.**

Hand tracking can still struggle with overlap, poor lighting, motion blur or
occluded fingertips. The app shows recognized roles/actions to help diagnose
misread poses. This build adds daily-use controls; it does not claim those physical
limits have been eliminated.

Wispr references: [shortcut settings](https://docs.wisprflow.ai/articles/2612050838-Supported-%26-Unsupported-Keyboard-Hotkey-Shortcuts),
[hands-free start/stop and insertion](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free).
