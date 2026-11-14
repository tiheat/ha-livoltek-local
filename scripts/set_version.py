"""Write the release version into manifest.json and pyproject.toml (called by semantic-release)."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise SystemExit(f"Invalid version: {version!r}")

    manifest_path = ROOT / "custom_components" / "livoltek_local" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    pyproject_path = ROOT / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    new_text, count = re.subn(r'^version = "[^"]*"$', f'version = "{version}"', text, count=1, flags=re.M)
    if count != 1:
        raise SystemExit("version line not found in pyproject.toml")
    pyproject_path.write_text(new_text, encoding="utf-8")
    print(f"Version set to {version}")


if __name__ == "__main__":
    main(sys.argv[1])
