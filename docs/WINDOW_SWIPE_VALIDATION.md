# Natural air swipes — 12 October 2026

## Live on/off option and repository package

**Enable window swipes** can now be unchecked while desktop mouse controls are
active. Disabling cancels pending swipe recognition, preserves mouse control
and saves the choice for restart; re-enabling also leaves the mouse active.
The dedicated UI check covers this behavior and preference persistence.

After this update, the working source passed **340 tests**. The exact portable
GitHub source package passed **333 tests with 7 optional asset checks skipped**
using the current installed dependencies and no bundled model assets. These are
source/export checks, not a full dependency/model installation on another PC.
Installation and update instructions are in `docs/SETUP_ANOTHER_WINDOWS_PC.md`.
The package preserves the repository's portable configuration, excludes personal
preferences, original videos and runtime files, and includes the current
natural-swipe modules plus independently generated synthetic regression fixtures.
Personal video-derived hand observations remain local and are not published.

## Core gesture validation

The active implementation matches the latest replacement recordings named
`Next_Swipe-Gesture.mp4` (65 frames, about 4.43 seconds) and
`Previous_Swipe-Gesture.mp4` (40 frames, about 2.71 seconds).

Restart SlateInk, choose Hand touchpad → Touchpad: desktop, start the camera and
enable desktop mouse control. Natural air swipes are enabled by default. Sweep
the relaxed control hand sideways as shown in Next; sweep back as shown in
Previous. Palm opening, straightening every finger and a deliberate wrist turn
are no longer required. Folded-hand lateral motion is supported too.

The detector reserves a relaxed sideways/folded hand for swipe recognition,
settles automatically in about 100 ms, and measures the short lateral trajectory
of the hand/fingers. Two real observations confirm travel across the threshold.
Each stroke switches once, with the adjustable 0.8-second cooldown. A stationary
hand, small motions and vertical arm movements do not switch. Upright joined
index + middle returns to normal mouse input. Higher swipe sensitivity needs
less lateral travel. Gaming and Drawing do not swipe.

Changes that address the forward recording:

- A low-confidence duplicate hand in the unmirrored Next video no longer
  invalidates the real hand's role. Confident duplicates still stop input.
- A single missing observation in mirrored Next can be bridged for at most
  160 ms while pointer actions remain frozen. No switch occurs on missing data;
  longer loss or stale data cancels the stroke.
- Direction follows image travel with preview-mirror correction, without
  relying on flickering handedness labels.
- First-shown hand identity settles briefly on activation, allowing the initial
  one-frame wrong label in Previous to recover. Established two-hand roles stay
  locked; active mouse/keyboard ownership is still released on interruptions.
- A transient V-like estimate during a reserved stroke cannot start Wispr.
  Active dictation and a deliberate helper V retain priority. Active click/drag,
  physical mouse buttons and keyboard modifiers block switching.

Validation:

- Full regression: **339 passed in 4.72 seconds**. The obsolete wrist-turn tests
  were replaced by the current air-swipe tests. Test temporary data lives under
  `artifacts/pytest-natural-air-swipes-final-20261012`.
- Fresh offline replay used the real local tracker and full Desktop session on
  both latest recordings, mirrored and unmirrored. Next produced exactly one
  `+1` event at 1.705 seconds unmirrored / 1.773 seconds mirrored. Previous
  produced exactly one `-1` event at 0.879 seconds in both orientations.
  There were zero pointer, click, scroll or voice events, and no held buttons.
- Interpolated reference strokes passed at 10, 15, 20 and 30 updates per second.
  Sparse recording playback checks prohibit opposite/duplicate actions and
  accidental mouse/voice input; it may safely omit recognition when observations
  are insufficient. Recognition is not promised below the supported tracking rate.
- The native Windows probe ran the same latest observations through the full
  Desktop session and restricted switching to three disposable test windows.
  Each named gesture changed actual foreground focus exactly once, with and
  without mirroring. It verified stable forward/reverse window order, minimized
  restoration, unsuitable/own-process filtering, Alt release and fixture cleanup.
- The new settings layout was visually reviewed at 1280 × 900. Preferences and
  the user's existing pointer/scroll settings were preserved.

Evidence and repeatable checks:

- `scripts/replay_swipe_references.py` →
  `artifacts/natural-swipe-references/replay-results.json`.
- `scripts/native_window_swipe_probe.py` → `artifacts/native-window-swipe.json`.
- The local validation used video-derived observations. The repository's
  `tests/fixtures/natural_swipe_reference_landmarks.json` instead contains
  generic synthetic coordinates, with no personal measurements or source hashes.
  Replaying published fixtures checks software behavior; repeating the physical
  reference validation requires separately supplied original recordings.
- `artifacts/ui-natural-air-swipe-desktop.png` shows the current settings.
- `docs/GESTURE_GUIDE.md` / `.html` explain the current gestures.

Native activation requests foreground focus once, releases its owned Alt key
and waits for confirmation without automatic retries or Windows setting changes.
Recognition of the recorded physical motions is verified; a fresh live-camera
trial and long-session comfort remain untested. No live camera or microphone was
opened during these checks. The window backend is currently Windows-specific.
