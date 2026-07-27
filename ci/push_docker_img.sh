#!/usr/bin/env bash
set -euo pipefail

img_version="0.1.0"
this_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
img_tag="ghcr.io/boutproject/bout-spack-ci:$img_version"

# Warn if not logged in to GHCR
if ! grep -q '"ghcr.io"' "${HOME}/.docker/config.json" 2>/dev/null; then
    echo "WARNING: You don't appear to be logged in to ghcr.io. Image push might fail."
    echo "Try:"
    echo "  1. Set GITHUB_PAT to an access token with write:packages scope, then"
    echo "  2. echo \"\$GITHUB_PAT\" | docker login ghcr.io --username <github username> --password-stdin"
    echo
fi

docker build -t "$img_tag" "$this_dir"
docker push "$img_tag"