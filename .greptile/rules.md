## Review Priorities

Focus on correctness, workflow safety, and repository policy violations.

## Repository Rules

- Flag any change that edits plugin files without the required patch version bump.
- Flag GitHub workflow changes that execute untrusted pull request code under `pull_request_target`.
- Flag release automation changes that could create duplicate or incorrect tags.
- Treat CI and review automation regressions as high-signal findings.

## Noise Control

- Do not comment on formatting-only issues.
- Do not suggest broad refactors unless they fix a concrete defect in this PR.
