#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-${ROOT}/.venv-build}"
PY="${VENV}/bin/python"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -x "${PY}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV}"
  "${PY}" -m pip install --upgrade pip
fi

"${PY}" -m pip install -e "${ROOT}"
"${PY}" -m pip install pyinstaller tomli

VERSION="$(${PY} - <<PY
from pathlib import Path
try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib

root = Path("${ROOT}")
pyproject = (root / "pyproject.toml").read_bytes()
print(tomllib.loads(pyproject.decode("utf-8"))["project"]["version"])
PY
)"

DIST="${ROOT}/dist"
BUILD="${DIST}/build"
mkdir -p "${DIST}"
rm -rf "${BUILD}"

"${PY}" -m PyInstaller \
  --noconfirm \
  --clean \
  --name subsim \
  --onefile "${ROOT}/subsim/__main__.py" \
  --add-data "${ROOT}/assets/sfx:assets/sfx" \
  --distpath "${DIST}" \
  --workpath "${BUILD}" \
  --specpath "${DIST}"

cat > "${DIST}/run_subsim.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${DIR}/subsim" "$@"
SH
chmod +x "${DIST}/run_subsim.sh"

"${PY}" - <<PY
import zipfile
from pathlib import Path

dist = Path("${DIST}")
version = "${VERSION}"
zip_path = dist / f"subsim-{version}-linux-x86_64.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(dist / "subsim", "subsim")
    zf.write(dist / "run_subsim.sh", "run_subsim.sh")
print(f"Wrote {zip_path}")
PY
