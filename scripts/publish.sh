#!/usr/bin/env bash
# Build + publish to PyPI (or TestPyPI when REPO=testpypi).
# Normally invoked indirectly by .github/workflows/release.yml; available locally
# for emergency manual releases.
set -euo pipefail

REPO="${REPO:-pypi}"

if [[ -z "${TWINE_PASSWORD:-}" ]]; then
    echo "error: TWINE_PASSWORD must be set to a PyPI API token" >&2
    exit 1
fi

rm -rf dist/ build/ ./*.egg-info
python -m build
python -m twine check dist/*

case "$REPO" in
    pypi)
        python -m twine upload --non-interactive dist/*
        ;;
    testpypi)
        python -m twine upload --non-interactive \
            --repository-url https://test.pypi.org/legacy/ dist/*
        ;;
    *)
        echo "error: REPO must be 'pypi' or 'testpypi' (got '$REPO')" >&2
        exit 1
        ;;
esac
