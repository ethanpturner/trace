"""Reading the requirements catalog.

`requirements/` is version-controlled YAML (DEC-010) and this package is the only thing that
reads it. `loader.py` parses it, validates it against `data-model.md` sections 17 and 30, and
computes the DEC-019 content hash.
"""
