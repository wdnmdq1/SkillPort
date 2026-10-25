"""Exercise the distributed executable with Python removed from child PATH."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def smoke(directory):
    directory = Path(directory).resolve()
    executable = directory / "skillport.exe"
    packages = list(directory.glob("skillport-starter-*.zip"))
    assert len(packages) == 1, "Expected one starter package"
    package = packages[0]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME") and not k.startswith("HERMES_")}
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env["PYTHONIOENCODING"] = "utf-8"
    observations = []

    def run(tool, *args, expected=0):
        result = subprocess.run([str(tool), *map(str, args)], env=env, capture_output=True, encoding="utf-8", timeout=60)
        assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout) if result.stdout.lstrip().startswith("{") else result.stdout.strip()

    with tempfile.TemporaryDirectory(prefix="skillport-portable-") as temp:
        root = Path(temp)
        version = run(executable, "--version")
        assert run(executable, "inspect", package)["valid"]
        for agent, folder in (("claude-code", ".claude"), ("codex", ".agents"), ("hermes", ".hermes")):
            home = root / f"中文 空格 {agent}"
            first = run(executable, "install", package, "--agent", agent, "--home", home)
            assert first["ok"] and all(r["files"] == "installed" for r in first["results"])
            second = run(executable, "install", package, "--agent", agent, "--home", home)
            assert all(r["files"] == "unchanged" for r in second["results"])
            installed = home / folder / "skills"
            manager = installed / "skillport/bin/skillport.exe"
            assert run(manager, "inspect", package)["valid"]
            assert len(run(manager, "list", "--agent", agent, "--home", home)["skills"]) == 3
            (installed / "skillport-brief/SKILL.md").write_text("用户修改", encoding="utf-8")
            conflict = run(manager, "install", package, "--agent", agent, "--home", home, expected=1)
            assert conflict["results"][1]["files"] == "conflict"
            assert (installed / "skillport-brief/SKILL.md").read_text(encoding="utf-8") == "用户修改"
            observations.append({"agent": agent, "isolated_filesystem_install": "passed", "reinstall": "passed",
                                 "installed_manager": "passed", "conflict_preserved": "passed", "host_recognition": "not-tested"})
    return {"version": version, "portable_executable": "passed", "python_on_child_path": False, "results": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("release_directory")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = smoke(args.release_directory)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        report = Path(args.output).resolve()
        report.write_text(text + "\n", encoding="utf-8")
        directory = Path(args.release_directory).resolve()
        if report.parent == directory and (directory / "SHA256SUMS").is_file():
            entries = [p for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"]
            (directory / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(directory).as_posix()}\n" for p in entries), encoding="utf-8")
    print(text)
