# Fun playground

Three interactive scenes live under **Hand touchpad → Touchpad: fun playground**.
Disable desktop controls first if they are active. Choose a scene, then click
**Enter playground**. Before entry, use **Sound for this scene** to turn that
scene's effects on or off. Each scene remembers a separate choice; all start off.
This starts the existing webcam
and local hand tracker and opens a fullscreen play space. No new dependencies,
browser, account or additional camera connection is needed.

## Portal fire

Move your **physical right hand** in view. Its index-tip position leaves a hot
rope of fire and drifting sparks; no pinch or open-palm pose is required.
Trace a reasonably round, closed circle about a hand-span or larger in the
preview, taking roughly 1–4 seconds. The circle seals into a glowing portal with
rotating markings and flying embers. Up to three portals can coexist; they fade
after about nine seconds. Trails fade naturally, so the scene stays responsive.

Keep your fingers/knuckles visible. The small **camera hand check** helps with
framing; it follows your saved camera mirror/rotation. Mirroring is corrected
for handedness automatically: both mirror settings still use your right hand.
The separate floating preview hides while this in-scene hand check is available;
your saved floating-preview preference stays unchanged.

## Web dome

Show **both hands**, leaving space between them. Spread them apart to expand
the dome; bring them together to shrink it. The right palm's horizontal and
vertical position turns/tilts the structure. The mesh has 3D vertices, depth
ordering and perspective, rendered locally on your computer. A right
thumb/index pinch sends a ripple.

## Nebula

Move your right hand to attract a cloud of stars into a moving vortex. Add your
left hand as a repelling gravity well. Briefly open the right thumb/index, then
pinch to release an outward star burst. Open again before another burst.

## Sound design

Select Portal fire, Web dome or Nebula on the setup screen, then choose **Sound
for this scene** before entering. The three choices are independent and save
locally. There is also a **Sound on / Sound off** button inside the playground;
switching scenes restores that scene's preference.

- **Portal fire:** a low fire bed, scattered stereo crackles, movement-driven
  air/heat, and a rising seal sound with a low impact and sparkling overtones.
- **Web dome:** quiet resonant tones follow tension; spreading the dome plucks
  the structure and a pinch ripple has a glass-like chime.
- **Nebula:** a spacious, gently moving pad, a vortex tone that follows motion,
  and a descending star cascade when a pinch releases a burst.

The sounds are original procedural synthesis. No sample download, microphone or
additional package is needed. Playback uses the system's default audio output
and the app's own conservative volume; it does not change the Windows mixer.
Mute, pause, focus loss, minimization and exit stop the audio stream and discard
queued effects. If output is unavailable, visuals continue and the sound button
reports that state. The implementation uses the already-installed
[Qt audio output API](https://doc.qt.io/qt-6/qaudiosink.html).

## Controls

| Control | Action |
|---|---|
| 1 / 2 / 3 or scene tabs | Portal fire / Web dome / Nebula |
| Space or Clear | Clear trails, portals and effects; reset the star cloud |
| P or Pause | Pause/resume the simulation |
| F11 or Full screen | Switch fullscreen/windowed |
| Hand check | Show/hide the small in-scene camera view |
| Sound on / Sound off | Toggle sound for the current scene; saves its own preference |
| Try demo | Labelled synthetic motion through the same simulation; ignores hand control until switched off |
| Escape or Back | Return to SlateInk and stop the camera session |
| Ctrl+Alt+M | Pause/resume an open playground, or open it when Fun is selected |

The last scene is saved in this computer's local preferences. The regular
Desktop, Gaming and Drawing sub-modes keep their own behavior.

## Input and camera behavior

Fun runs **inside its own scene**. Desktop mouse clicks, WASD, window swipes and
Wispr gestures remain disabled there, including gestures that otherwise start
dictation. Leaving the frame or losing focus breaks the current stroke instead
of connecting distant points. Existing portals and particles can finish fading.
Stale camera images are replaced by a waiting message. The camera view remains
available while the simulation is paused. Closing the playground, stopping the
camera, switching modes or closing SlateInk ends the session.

Try demo labels the motion as synthetic; it does not pretend to recognize your
hand. In the app the camera session stays visible until you leave the playground
or stop capture, including while the demo runs. No video, snapshots or hand
history are saved by ordinary play. The developer visual probes save only their
explicitly generated synthetic previews when run deliberately.

## Verification and practical limits

Automated checks cover circle closure and rejection of partial/linear/tiny
strokes, physical-right-hand selection in both mirror modes, stale/ambiguous
tracking, stroke separation, two-hand expansion, bounded particles, pinch bursts,
scene rendering, mode selection, desktop-input isolation and exit cleanup.

`scripts/playground_visual_probe.py` renders labelled synthetic scenes without a
camera. `scripts/native_playground_probe.py` checks a real fullscreen window,
synthetic camera-packet routing, portal sealing, dome expansion, scene changes,
desktop input staying off and the camera-stop request on exit. It opens no
camera. Native lifecycle checks elsewhere cover actual capture-owner shutdown.

These establish software behavior and rendering, rather than physical hand
accuracy or guaranteed frame rates. Lighting, tracking rate, motion blur and
occlusion still affect live use.

Release checks on 16 October 2026: **477 local tests passed**; the portable
source package passed **458 tests**, with **10 optional-asset checks skipped**.
All three native fullscreen scenes accepted synthetic camera packets, kept
desktop input off, and passed the return/camera-stop check. Synthetic previews
were rendered and inspected for each scene.
Audio checks cover independent setup toggles, per-scene mute, output gating,
bounded/finite stereo synthesis, voice limits, partial writes and missing output.
`scripts/playground_audio_probe.py` writes generated sound examples only when
run deliberately. Its `--check-device` option verifies native PCM playback at
zero volume; all three scenes passed without opening a microphone.
