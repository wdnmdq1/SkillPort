from __future__ import annotations

import argparse
import json
import sys
from urllib.error import URLError

from . import __version__
from .core import AGENTS, Invalid, inspect_package, install, list_installed, pack
from .registry import install_from_registry, load_registry, search


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="skillport", description="SkillPort: portable Agent Skills packages (Windows x64)")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)
    inspect = subs.add_parser("inspect", help="Validate ZIP without executing its contents")
    inspect.add_argument("package")
    inspect.add_argument("--sha256")
    package = subs.add_parser("pack", help="Build a package from a JSON config")
    package.add_argument("config")
    package.add_argument("--output", required=True)
    direct = subs.add_parser("install", help="Install a local ZIP and the trusted manager")
    direct.add_argument("package")
    direct.add_argument("--sha256")
    get = subs.add_parser("get", help="Install an exact reviewed registry package")
    get.add_argument("id")
    get.add_argument("--package-version")
    listing = subs.add_parser("list", help="List filesystem skills; does not claim host recognition")
    for command in (direct, get, listing):
        command.add_argument("--agent", choices=AGENTS)
        command.add_argument("--home", help="Isolated development-test home (never auto-selected)")
    finder = subs.add_parser("search", help="Search the curated index")
    finder.add_argument("query", nargs="?", default="")
    registry = subs.add_parser("check-registry", help="Validate registry metadata without running skill code")
    for command in (get, finder, registry):
        command.add_argument("--registry")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            manifest, _ = inspect_package(args.package, args.sha256)
            result = {"valid": True, "manifest": manifest, "security_certified": False}
        elif args.command == "pack":
            result = pack(args.config, args.output)
        elif args.command == "install":
            result = install(args.package, args.agent, args.home, args.sha256)
        elif args.command == "list":
            result = list_installed(args.agent, args.home)
        elif args.command == "search":
            result = {"packages": search(args.query, args.registry)}
        elif args.command == "get":
            result = install_from_registry(args.id, args.package_version, args.registry, args.agent, args.home)
        else:
            result = {"valid": True, "packages": len(load_registry(args.registry)["packages"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (Invalid, OSError, URLError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
