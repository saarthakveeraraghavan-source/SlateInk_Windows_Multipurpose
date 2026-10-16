# SlateInk hand touchpad guide

Select Hand touchpad for these gestures. Camera starts **off**. Hand tracking
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
| Left click | Touch thumb + index, then separate; other fingers can stay relaxed | Click stays at the target instead of drifting with pinch closure |
| Double click / select a word | Two quick index/thumb pinch-and-release cycles | Normal Windows double click; word selection depends on the destination app |
| Select text / drag a window | Hold index/thumb pinch, then deliberately move the whole hand | Left button stays down. A settling interval and movement threshold prevent tiny motion from becoming a drag. Release to drop/finish |
| Right click | Thumb + middle pinch, then release; keep another finger extended | Normal right click. Separate index/middle enough for the thumb to clearly target one finger |
| Vertical scroll | Control hand: index + middle + ring extended, little finger curled, thumb away; move up/down | Up moves toward earlier content; down toward later content. Reverse scrolling flips this |
| Horizontal scroll | Same three-finger pose; move sideways first | Scrolls sideways in apps that support it. Lower the ring finger to end scrolling and choose a new axis |
| Precision pointing | Helper hand: open palm, all four fingers extended and thumb away | Slower, finer pointer movement while the control hand points or selects |
| Next window | RIGHT hand open: sweep across your chest as in the next-window sweep | One next-window switch. Mirror correction is automatic. Desktop only |
| Previous window | RIGHT hand open: reverse the sweep as in the previous-window sweep | One previous-window switch. Mirror correction is automatic. Desktop only |
| Pause / resume | Both hands: open palms held for about one second | Toggles pause. Lower/relax the pose before showing it again. Camera keeps running so resuming is possible |
| Start Wispr Flow | Either hand: index + pinky extended, middle/ring folded, thumb tucked (rock sign) | Starts after two clear observations, without a long hold or preliminary neutral pose. Relax or lower your hand while talking. Pointing and clicking freeze during dictation |
| Finish Wispr and insert text | SAME hand: index + pinky + thumb extended, middle/ring folded (swag sign) | Sends the stop shortcut once. The other hand's swag sign does nothing. Wispr performs transcription and insertion |
| Start/pause/resume by keyboard | Ctrl+Alt+M while SlateInk is running | Global shortcut; no need to focus the SlateInk window |
| Emergency stop / cancel voice | Escape or Stop everything | Stops camera, releases app-owned mouse buttons and keys, and cancels an active Wispr gesture |

Keep the index/thumb contact visible beyond the knuckles, as in an OK sign;
the other fingers may relax. A resting fist stays excluded. Clicks require opening the pinches after enabling or
interrupted tracking. An ambiguous thumb touch between two fingertips does not click.

## Floating camera preview — all modes

Check **Floating camera preview** beside the camera controls, then start the
camera. A small live view stays above other desktop windows in every mode,
including Desktop, Gaming, Drawing, paper OCR, finger letters, pen and eye gaze.
It uses the existing oriented feed and annotations: no second webcam connection
or second tracking model is started. Preview rendering is limited to 15 updates
per second while tracking keeps its own rate.

**Drag the dark header** to place it. It saves its position in this computer's
preferences and returns to that position next time. If the monitor arrangement
changes, it is clamped back onto an available screen. Clicking/dragging it does
not steal keyboard focus from the destination app. Click its **×**, or uncheck
the main checkbox, to hide it. This hides the small preview, not the main app.
The preview shows only while camera capture is active and clears stale frames.
It is an ordinary always-on-top desktop window; exclusive-fullscreen games and
protected desktops are not validated. Use a windowed/borderless game if needed.

When minimized, an enabled hand touchpad can keep working with **Keep running
when minimized** and a visible tray/preview indicator. In other modes the camera
feed may keep running for this explicitly enabled preview, but automatic writing,
pen/gaze pointer control and pending typing are stopped. Closing the only visible
background preview stops that camera session unless the enabled hand touchpad
still has its tray indicator. Stop everything / Escape still stops capture.

**Main-window × / Stop & quit:** closes SlateInk, releases inputs, stops the
camera-owning process and hides the small preview. **Main-window –:** minimizes
under the background settings above. A pinch on the title-bar controls releases
the owned button before the window action, so it no longer relies on a native
caption tracking loop to process the pinch release.

A second launch from this installation brings the existing app forward instead
of starting another hidden camera session. Closing is bounded even if the webcam
driver stalls while reading: the device owner is an isolated process and is
stopped before camera-off is reported. No frames are saved by this feature.

## Clicking reliably

Left click is still **thumb + index pinch, then release**. The other fingers may
relax if the camera can see the index/thumb contact in front of the knuckles.
It no longer depends on fully opening the unrelated
middle pinch. When index and middle are close to the thumb, a clearly folded
index with a straight middle identifies left-click; unclear shapes stay blocked.
The resting-hand guard now checks the selected target rather than rejecting a
valid index pinch because the thumb is also near middle.

Right click is still **thumb + middle pinch, then release**, with the index pinch
open. Its target must be clearly closer than index and stay pinched for about
**0.1 seconds**. Left-click uses two observed contact frames, at least
**0.025 seconds** apart, and tolerates small distance jitter after contact.
Keep the palm reasonably steady as you close a pinch. Once left is down, deliberate
held movement still drags/selects normally; two left pinch/release cycles still
double-click. Mouse movement from finger closure does not start a drag.

Clicks are suppressed during moving swipes and for **0.2 seconds** while leaving a swipe,
so a closing hand is not interpreted as a context-menu click. No new unlock pose
is needed. An idle open palm now arms the pinch instead of repeatedly clearing
it, so you can click straight from that pose. After a moving swipe's settling
interval, open the pinch briefly, then point/pinch normally.

## Swipe to change windows

In **Touchpad: desktop**, use your **physical RIGHT hand for both gestures**.
Open all four fingers with the thumb comfortably away, as shown in the new
recordings. Let the camera see the open hand briefly, then sweep the whole hand
sideways. Keep the other hand relaxed.

- **Next:** copy **the next-window sweep**: move the right hand across your
  chest toward your left.
- **Previous:** copy **the previous-window sweep**: sweep back toward your
  right.

These directions follow the new file labels. With **Mirror camera ON**, Next
moves left across the preview; Previous moves right. Both gestures still use
your right hand. The app corrects handedness labels and motion for mirroring;
you do not have to reverse the gestures yourself.

Accuracy update: the same open-hand sweep can now start while already moving,
including a fast reverse that exposes only one clear starting frame. Two actual
ending observations are still required; a missing start cannot be invented.
Hand shape uses finger-joint depth as well as its camera projection, improving
recognition while the palm turns. Start observations are retained during
cooldown so the next reverse is not discarded.

There is no fist hold, countdown or mandatory index/middle unlock gesture.
The earlier persistent **cancelled/finished** state has been removed. If a swipe
is interrupted, relax or lower the hand, then show the open right hand and try
again. You can also continue from a visible open hand once tracking settles.
Let the hand settle between strokes; each stroke switches once, with the saved
cooldown. Holding the finish position does not repeatedly switch windows.

Pointing and clicks pause while the open right hand reserves the swipe channel.
Relax the fingers, then use joined index + middle to point normally. Two-finger
pointing, three-finger scrolling, a folded hand and finger-only movement do not
start a swipe. A brief little-finger tracking error can be tolerated during an
already reserved open-hand stroke. Normal mouse, helper-palm precision, two-palm
pause and Wispr controls retain their existing gestures.

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
priority. Swipes cannot interrupt owned click/drag input, physical mouse buttons
or held keyboard modifiers. The supplied fast sweeps lose hand landmarks for
several frames. A reserved stroke can retain an observed start for up to 0.7
seconds of missing landmarks, provided camera frames are still fresh. No switch
occurs on missing data: two matching, trusted destination observations confirm
whole-palm AND wrist travel. Longer loss, stale frames, unsuitable scale changes,
large instantaneous jumps and ambiguous duplicate hands discard the stroke.
Cancellation resets normally and does not require a special unlock pose.

Windows foreground restrictions still apply. The switch uses a brief owned Alt
press and the standard foreground API, releases Alt immediately, and stops hand
control if Windows does not confirm activation. No system focus settings change.
The activation rules are documented by Microsoft in
[SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)
and [LockSetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-locksetforegroundwindow).

Portable tests exercise independently generated open-palm strokes, both mirror
settings, fast reversals, interruptions and arbitration with clicks and voice.
Original recordings and extracted personal observations are excluded. See
[swipe verification](WINDOW_SWIPE_VALIDATION.md) and
[click/voice verification](CLICK_WISPR_VALIDATION.md).

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

## Optional Wispr Flow integration

The default shortcut binding is **Ctrl+Win: press once to start, press again to
stop**. Enable the optional voice gesture when that dropdown matches Wispr's
settings. SlateInk does not change those settings. Wispr Flow must already be running, signed in and working normally.

1. Focus an ordinary textbox so its caret is visible. Release keyboard modifiers.
2. Briefly show **index + pinky extended, middle/ring folded and thumb tucked**
   with either hand (rock sign). Keep the thumb across the folded fingers,
   rather than sticking it out. Two fresh observations start promptly; no long
   hold or preliminary neutral gesture is required. V no longer starts Wispr.
3. Wait for **Wispr's own ping/recording indicator**, then speak. SlateInk's
   status confirms the gesture/shortcut request, not that Wispr accepted it.
4. Relax, move or lower your hand while speaking. You can remove both hands from
   view; recording stays latched even during a tracking delay. To finish, show
   **index + pinky + thumb extended with the SAME hand** (swag sign),
   keeping middle/ring folded. Spread the thumb clearly away from the palm. It confirms over two or more clear frames (at least 0.06 seconds).
   Lowering the rock sign never sends stop. Thumbs-up is inactive. Wait for Wispr to insert your words.
   Do not press the physical Wispr toggle while
   the hand-controlled session is active, as that can desynchronize the toggles.
5. Open the pinches again to resume pointing. Changing the focused window/control,
   stopping capture, explicitly pausing controls or Escape cancels the
   hand-controlled voice session instead of sending another start/stop toggle.
   Two open palms are ignored while dictating, so changing hand poses cannot
   accidentally pause and cancel it. Ctrl+Alt+M remains an explicit pause/cancel.

The **Rock starts / swag stops Wispr** checkbox disables the voice gesture if you do not
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
- Background hand input requires enabled hand touchpad, the saved background
  option and a visible tray or floating-preview indicator. An explicitly enabled
  floating preview can keep camera-only capture in other modes while their input
  controls stop on minimize/hide. Without either permission, capture stops.
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
blank textbox and dictate one short sentence using the rock sign. Confirm
Wispr's recording indicator, hands-free listening, same-hand swag-sign stop and
insertion in that same field.

Native mouse tests have verified clicks, dragging, window dragging, scrolling,
relative movement and double-click word selection. Native keyboard delivery and
the global hotkey were tested in a disposable receiver with substitute keys,
without activating Wispr or recording audio. Minimize/pause/resume and gesture
policies were tested with synthetic hands. **Actual Wispr acceptance, physical
gesture comfort and long-session daily reliability still need your real-use trial.**

The latest click/rock-start/same-hand-swag-stop changes passed **453 tests** and
both-mirror native click/shortcut checks. See [click and Wispr validation](CLICK_WISPR_VALIDATION.md).

Hand tracking can still struggle with overlap, poor lighting, motion blur or
occluded fingertips. The app shows recognized roles/actions to help diagnose
misread poses. This build adds daily-use controls; it does not claim those physical
limits have been eliminated.

Wispr references: [shortcut settings](https://docs.wisprflow.ai/articles/2612050838-Supported-%26-Unsupported-Keyboard-Hotkey-Shortcuts),
[hands-free start/stop and insertion](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free).
