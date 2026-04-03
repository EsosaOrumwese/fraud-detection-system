# Model Risk Note v1

Main risk if overtrusted:
- the score could be mistaken for an autonomous fraud adjudication output rather than a prioritisation aid

Main bounded controls:
- authoritative truth is the target source
- comparison-only bank view is excluded from target logic
- no post-outcome case fields are used as live-like features
- thresholding is defined for human-led review support only

Human-in-the-loop posture:
- High band supports strongest review priority
- the score should not replace case review or override other governance controls
