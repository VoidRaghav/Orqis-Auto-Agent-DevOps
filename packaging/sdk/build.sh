#!/usr/bin/env bash
# Assemble and build the orqis-agent-sdk distribution from the main repo source.
#
# Ships ONLY the client: instrumentation (the OpenAI/Anthropic/LangChain
# patchers + background emitter), the event wire-schema, and a slim 2-field
# config. No detectors, RCA, patch generator, server, store, or auth code is
# included. A safety check below aborts the build if anything private slips in.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$REPO/orqis"
STAGE="$HERE/.build"
PKG="$STAGE/orqis"
PY="${PYTHON:-$REPO/.venv/bin/python}"

rm -rf "$STAGE" "$HERE/dist"
mkdir -p "$PKG/instrumentation" "$PKG/backend"

# Client entry point + instrumentation layer.
cp "$SRC/__init__.py" "$PKG/__init__.py"
cp "$SRC"/instrumentation/*.py "$PKG/instrumentation/"

# Event wire-schema only - nothing else from backend/.
: > "$PKG/backend/__init__.py"
cp "$SRC/backend/models.py" "$PKG/backend/models.py"

# Slim client config (2 fields) replaces the full backend config.
cp "$HERE/overrides/config.py" "$PKG/config.py"

# Packaging metadata.
cp "$HERE/pyproject.toml" "$HERE/README.md" "$HERE/LICENSE" "$STAGE/"

# Safety net: fail loudly if any private module made it into the staging tree.
for banned in rca server store workspace_auth tenancy deps durable daemon mcp integrations audit db cli; do
  if find "$PKG" -name "*${banned}*" | grep -q .; then
    echo "ERROR: private module matching '${banned}' present in SDK staging - aborting" >&2
    find "$PKG" -name "*${banned}*" >&2
    exit 1
  fi
done

cd "$STAGE"
"$PY" -m build --outdir "$HERE/dist"
echo ""
echo "Built into $HERE/dist:"
ls -1 "$HERE/dist"
