"""Refresh or verify sizes and hashes of tracked public files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without changing the manifest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "public_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    files = []
    for name in sorted(tracked.decode("utf-8").split("\0")):
        if not name or name == "public_manifest.json":
            continue
        data = (root / name).read_bytes()
        files.append({"path": name, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()})
    expected = {
        "files": files,
        "files_count_excluding_manifest": len(files),
        "bytes_excluding_manifest": sum(row["bytes"] for row in files),
    }
    if args.check:
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise SystemExit("Manifest mismatch: regenerate public_manifest.json")
        print("Manifest OK")
    else:
        manifest.update(expected)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Manifest updated:", len(files), "files")


if __name__ == "__main__":
    main()
