# Window swipe verification

The current Desktop gesture uses an open physical RIGHT hand for next and
previous windows, with automatic mirror correction. Both palm and wrist must
travel horizontally; pointing, scrolling, fists and finger-only motion cannot
start it. Two real endpoint observations confirm a stroke. Observed starts may
survive short landmark gaps while camera frames remain fresh. Each stroke fires
once with cooldown. Moving swipes reserve input and require a short click
settling interval; an idle open palm can arm the index/thumb click.

Portable tests use independently generated synthetic fixtures and cover
direction, mirrors, update rates, reversal, interruption, click/voice priority,
and the live enable/disable option. `scripts/native_window_swipe_probe.py`
checks focus changes only in disposable Windows windows. Its optional
`--references` path requires separately supplied original recordings and data.
Original personal recordings and extracted landmarks are not included.

These checks establish policy and Windows input delivery; they do not measure
physical hand accuracy or long-session comfort. See the gesture guide for use.
