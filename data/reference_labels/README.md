# Reference labels

Hand-labeled intervals used to score the mode detector. Format and rules: `docs/validation_protocol.md`.

| File | Role | How it was labeled | Human review |
|---|---|---|---|
| drive12_1480-1780.csv | tuning window | Drafted with Claude from the raw speed trace, Sept 29 | Rijul, Oct 15 |
| drive3_600-900.csv | held-out window | Drafted with Claude Code from the speed and throttle trace before running the detector; automated check found every interval consistent with its speed change | Rijul, Oct 15 |

Change "pending" to the reviewer's name and date once each file has been checked against its plot.
