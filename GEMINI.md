# Antigravity Project Guidelines

## RepoCloud CI/CD Standard

Whenever initializing, scaffolding, or onboarding any repository targeting RepoCloud:
1. **Remote Origin**: Configure upstream git remote to `http://127.0.0.1:3030/<owner>/<repo>.git` on the `main` branch.
2. **Local Test Runner (`scripts/ci.sh`)**: Provide an executable test and lint script adapted to the project's stack (e.g. `cargo test`, `unittest`/`pytest`, `npm test`, `go test`). Use `#!/bin/sh` and sandbox-resilient interpreter paths (e.g., `PYTHON="${PYTHON:-/usr/bin/python3}"`).
3. **Server Pipeline Contract (`.repocloud-ci.sh`)**: Provide an executable script that invokes `./scripts/ci.sh`.
4. **Pre-Push Gate (`.git/hooks/pre-push`)**: Install an executable pre-push hook running `./scripts/ci.sh` to block failing commits from reaching the remote.
