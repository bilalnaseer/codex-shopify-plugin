#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/plugins/shopify"
MARKETPLACE_DIR="${HOME}/.agents/plugins"
MARKETPLACE_FILE="${MARKETPLACE_DIR}/marketplace.json"

mkdir -p "${HOME}/plugins" "${MARKETPLACE_DIR}"

if [[ "${PLUGIN_DIR}" != "${TARGET_DIR}" ]]; then
  mkdir -p "${TARGET_DIR}"
  python3 - "${PLUGIN_DIR}" "${TARGET_DIR}" <<'PY'
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

for item in source.iterdir():
    if item.name == ".git":
        continue
    destination = target / item.name
    if item.is_dir():
        shutil.copytree(item, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(item, destination)
PY
fi

python3 - "${MARKETPLACE_FILE}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if path.exists():
    payload = json.loads(path.read_text())
else:
    payload = {"name": "local", "interface": {"displayName": "Local Plugins"}, "plugins": []}

payload.setdefault("name", "local")
payload.setdefault("interface", {}).setdefault("displayName", "Local Plugins")
plugins = payload.setdefault("plugins", [])

entry = {
    "name": "shopify",
    "source": {"source": "local", "path": "./plugins/shopify"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Commerce",
}

for index, existing in enumerate(plugins):
    if isinstance(existing, dict) and existing.get("name") == "shopify":
        plugins[index] = entry
        break
else:
    plugins.append(entry)

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n")
PY

echo "Installed Shopify plugin at ${TARGET_DIR}"
echo "Registered marketplace entry in ${MARKETPLACE_FILE}"
echo "Restart Codex, then enable Shopify from Local Plugins."
