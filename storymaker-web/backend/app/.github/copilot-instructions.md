# StoryMaker backend instructions

- This repository contains a Python backend for StoryMaker with FastAPI routes in api/, SQLAlchemy models in db/, and helpers in core/ and services/.
- Preserve current API contracts and database behavior unless the request explicitly requires a breaking change.
- Keep backup files and previous revisions untouched; do not edit *.bak or *_backup* variants unless instructed.
- Prefer minimal, well-scoped changes that fit the existing pattern in the surrounding module.
- Validate Python edits with a compile or import-based check when possible.
