---
description: Tag GitHub issues with the model tier their delivery needs
---

Run the issue triage script with the arguments given, applying writes:

- With arguments: `uv run python scripts/triage.py $ARGUMENTS --apply`
- With no arguments: `uv run python scripts/triage.py --all-untriaged --apply`

Then report which issues were tiered, to which tier, and any that were deny-clamped or
marked low-confidence. Do not classify issues yourself; the script owns the labels.
