# Click and latched Wispr gesture update — 16 October 2026

## Behavior

- Index/thumb contact presses left; separation releases. The press needs two
  observations at least 25 ms apart. The existing release debounce stays 60 ms.
  Small contact-distance jitter no longer resets a pending press. Right click
  keeps its longer confirmation and clear-target requirements.
- An idle open right palm still reserves swiping but now supplies open-pinch
  evidence. Previously, every reserved frame interrupted and reset the mouse,
  so closing directly from that pose could never pass release-to-arm.
- Only meaningful palm/wrist travel starts the post-swipe settling interval.
  Moving swipes still suppress clicks and clear readiness. A natural index pinch
  may keep the other fingers curled if the contact stays beyond the knuckles;
  a resting fist and ambiguous thumb/index/middle contact remain excluded.
- Index + pinky with middle/ring folded and thumb tucked (rock sign) starts Wispr
  after two clear observations, at least 25 ms apart. There is no long hold or
  startup neutral requirement. The initiating handedness is stored.
- Lowering V, removing both hands, temporary tracking staleness, two open palms,
  duplicate labels or the other hand's swag sign do not finish or pause recording.
  Index + pinky + thumb extended, middle/ring folded (swag sign), from the
  initiating hand sends stop once after at least 60 ms of fresh observations.
  Thumb spread follows the palm's own axis, with a gap between folded/extended
  thresholds. V and thumbs-up no longer start or stop Wispr. A swag sign while
  idle does not start recording; holding the rock sign does not stop it.
- Pointer/buttons/swipes remain suspended while the voice session is latched.
  Escape, explicit pause/disable, camera stop/failure, mode changes and destination
  focus changes still cancel. Actual camera shutdown retains its existing cleanup.
- The main-window options/guide and floating preview identify the new start/stop
  gesture; the preview identifies the physical hand that should give the swag sign.

## Verification

Full local regression: **453 passed in 6.36 seconds**.

Coverage includes brief left
pinches at 15/24/30/60 observations per second, contact jitter, curled supporting
fingers, real-reference swipe replay assertions, click ownership/dragging,
same-hand voice ownership, startup rock sign, missing/stale hands, wrong-hand swag,
ambiguous/low-confidence stop observations, repeat sessions, and a main-window
stale-frame/preview/camera-stop integration check. Explicit negative tests reject
V, thumbs-up, pointing, scrolling, palms, fists and an idle swag sign. Rotation
and mirror checks verify that thumb states remain distinct. Gaming, Drawing and the other
camera modes remain covered by the complete suite.

`scripts/native_click_gesture_probe.py` passed with mirroring off and on:
three paired left presses/releases, double-click selection of the fixture word
`beta`, one paired right press/release, no lingering button ownership. The first
click begins directly from an open palm and uses an 80 ms closure.

`scripts/native_wispr_gesture_probe.py` passed with mirroring off and on:
one native shortcut received on rock, no additional shortcut after hand loss,
wrong-hand swag or repeated stale tracking, then exactly one additional
shortcut on same-hand swag. Keys were released. Ctrl+Win and Escape are
remapped to fixture-only Ctrl+F8/F9, so no microphone or transcript is involved.
Both probes used ordinary Windows permissions and disposable windows.

The probes allow the newly opened window and foreground-activation key events
to settle before starting their gesture sequences and stop on foreground loss.

These checks validate policy and Windows delivery using synthetic hands, plus the
existing local recorded-swipe fixtures. They do **not** measure physical pinch/
rock/swag recognition accuracy, actual Wispr recording/transcription acceptance,
or long-session comfort. A live user tryout remains necessary for those.
