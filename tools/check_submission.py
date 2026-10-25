"""Run this from the TRUSTED base revision, reading a PR tree as data only."""

import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillport.core import inspect_package, no_links, pack, read_json, require
from skillport.registry import download, validate_registry
from skillport.core import MAX_ARCHIVE


def check(root, online=False):
    root = Path(root).resolve()
    no_links(root / "registry/index.json")
    require((root / "registry/index.json").stat().st_size <= 5 * 1024 * 1024, "Registry exceeds 5 MiB")
    index = validate_registry(read_json((root / "registry/index.json").read_bytes()))
    count = 0
    with tempfile.TemporaryDirectory(prefix="skillport-review-") as temp:
        for config in sorted((root / "examples").glob("pack-*.json")):
            result = pack(config, Path(temp) / f"{count}.zip")
            inspect_package(result["path"])
            count += 1
        template = root / "templates/author/pack.json"
        if template.is_file():
            pack(template, Path(temp) / "author.zip")
            count += 1
        if online:
            for number, entry in enumerate(index["packages"]):
                target = Path(temp) / f"remote-{number}.zip"
                target.write_bytes(download(entry["archive"]["url"], MAX_ARCHIVE))
                manifest, _ = inspect_package(target, entry["archive"]["sha256"])
                require(manifest["id"] == entry["id"] and manifest["version"] == entry["version"]
                        and manifest["license"] == entry["license"]
                        and set(manifest["agents"]) == set(entry["compatibility"]), "Registry/manifest mismatch")
    print(f"Validated {count} local packages and {len(index['packages'])} registry entries; no skill code executed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tree")
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    check(args.tree, args.online)
