#!/usr/bin/env bash
# Regenerate cerberus_compliance/_generated/ from the upstream OpenAPI spec.
# Used by CI to detect drift: if running this script produces a non-empty git diff,
# the SDK is out of sync with the backend and must be regenerated + re-committed.
set -euo pipefail

SPEC_URL="${CERBERUS_OPENAPI_URL:-https://staging-compliance.cerberus.cl/v1/openapi.json}"
OUT_DIR="cerberus_compliance/_generated"
TMP_SPEC="$(mktemp -t cerberus-openapi.XXXXXX.json)"
trap 'rm -f "$TMP_SPEC"' EXIT

echo ">> Fetching OpenAPI spec from $SPEC_URL"
curl --fail --silent --show-error --location "$SPEC_URL" -o "$TMP_SPEC"

echo ">> Generating client into $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

openapi-python-client generate \
    --path "$TMP_SPEC" \
    --output-path "$OUT_DIR" \
    --overwrite

echo ">> Done. Inspect git diff for changes."
