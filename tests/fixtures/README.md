# Deterministic fixtures

Run `python tests/fixtures/build.py` to create independent `api` and `web` Git repositories plus a separate workspace. The builder uses fixed content but allows Git to assign normal local commit metadata; tests assert relationships and content rather than a hard-coded SHA.
