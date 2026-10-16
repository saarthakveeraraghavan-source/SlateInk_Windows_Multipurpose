# Portable swipe fixtures

`open_palm_swipe_synthetic.json` contains independently generated generic open
right-hand sweeps with both mirror settings. `fist_swipe_synthetic.json` checks
that the retired fist gesture cannot switch windows. The older
`natural_swipe_reference_landmarks.json` is a legacy synthetic fixture retained
for compatibility. None contains measurements from personal videos.

Original recordings and their extracted observations remain local. Tests that
need those optional observations are skipped in this source-only package.
Native probes use disposable windows. These tests verify software behavior;
physical recognition and comfort need a live tryout.
