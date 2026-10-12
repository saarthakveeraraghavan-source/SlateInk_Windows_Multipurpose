# Portable synthetic swipe fixtures

`natural_swipe_reference_landmarks.json` contains independently generated,
generic hand coordinates. It has no measurements, hashes, images, audio or
other data extracted from the developer's personal reference videos.

The sequences exercise next/previous direction, preview mirroring, a temporary
low-confidence duplicate, one missing observation, and transient handedness
misclassification. Tests also vary update rates, sensitivity and interruption
conditions. These deterministic checks verify the detector's behavior; they
do not establish physical gesture accuracy on a user's camera.

`scripts/native_window_swipe_probe.py` uses these synthetic sequences with
disposable Windows windows. `scripts/analyze_swipe_references.py` and
`scripts/replay_swipe_references.py` require separately supplied local videos
to check actual tracking. Personal recordings and their extracted observations
remain outside this published package.
