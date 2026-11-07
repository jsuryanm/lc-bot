---
paths:
  - "**/*.py"
---

# Python style

- Python 3.12+, ruff line length 100. Run `ruff check . && ruff format .` before finishing.
- Read config only via `get_settings()` in `app/core/config.py`. Do not read `os.environ` elsewhere.
- Do not edit or lint anything under `data/`.
