"""Build standalone Windows tool, data-only packages and a pinned release index."""

import argparse
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skillport import __version__
from skillport.core import Invalid, json_bytes, pack, require, sha256
from skillport.registry import validate_registry


def build(output, repository=None, commit=None):
    require(sys.platform == "win32", "Build the Windows executable on Windows")
    if repository:
        require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "Invalid repository")
        require(commit and re.fullmatch(r"[0-9a-f]{40}", commit), "Publishing needs an exact source commit")
    output = Path(output).resolve()
    require(not output.exists() or not any(output.iterdir()), "Release output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    release = {"version": __version__, "repository": repository,
               "registry": f"https://github.com/{repository}/releases/latest/download/index.json" if repository else None,
               "commit": commit}
    with tempfile.TemporaryDirectory(prefix="skillport-build-", dir=output) as temp:
        temp = Path(temp)
        staged = temp / "src"
        shutil.copytree(ROOT / "src/skillport", staged / "skillport", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (staged / "skillport/data/release.json").write_bytes(json_bytes(release))
        licenses = staged / "skillport/data/licenses"
        licenses.mkdir(exist_ok=True)
        (licenses / "Python-LICENSE.txt").write_bytes((Path(sys.base_prefix) / "LICENSE.txt").read_bytes())
        for package, suffix, name in (("PyYAML", "licenses/LICENSE", "PyYAML-LICENSE.txt"),
                                      ("PyInstaller", "licenses/COPYING.txt", "PyInstaller-COPYING.txt")):
            dependency = distribution(package)
            license_path = next(dependency.locate_file(f) for f in dependency.files if str(f).replace("\\", "/").endswith(suffix))
            (licenses / name).write_bytes(license_path.read_bytes())
        shutil.copytree(licenses, output / "licenses")
        (output / "THIRD_PARTY_NOTICES.txt").write_text("\n\n".join(f"===== {p.name} =====\n{p.read_text(encoding='utf-8')}" for p in sorted(licenses.iterdir())), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", "skillport",
                        "--distpath", str(output), "--workpath", str(temp / "build"), "--specpath", str(temp),
                        "--paths", str(staged), "--add-data", f"{staged / 'skillport/data'}{os.pathsep}skillport/data",
                        str(ROOT / "tools/entrypoint.py")], cwd=temp, check=True)
    executable = output / "skillport.exe"
    tool_hash = sha256(executable.read_bytes())
    index = json.loads((ROOT / "registry/index.json").read_text(encoding="utf-8"))
    for kind in ("manager", "brief", "checklist", "starter"):
        result = pack(ROOT / f"examples/pack-{kind}.json", output / f"skillport-{kind}-{__version__}.zip",
                      release if repository else None, tool_hash)
        if repository:
            require(not any(p["id"] == result["manifest"]["id"] and p["version"] == __version__ for p in index["packages"]), "Official package collides with community index")
            index["packages"].append({
                "id": result["manifest"]["id"], "version": __version__, "description": f"SkillPort {kind} 官方示例包",
                "author": repository.split("/")[0], "license": "MIT", "source": {"repository": repository, "commit": commit},
                "archive": {"url": f"https://github.com/{repository}/releases/download/v{__version__}/{Path(result['path']).name}", "sha256": result["sha256"]},
                "compatibility": {agent: {"status": "declared"} for agent in result["manifest"]["agents"]}})
    validate_registry(index)
    (output / "index.json").write_bytes(json_bytes(index))
    (output / "release.json").write_bytes(json_bytes(release))
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    (output / "START-HERE.md").write_text(
        "# SkillPort 0.1.0 本地首版\n\n将 starter ZIP 拖入 Agent 并发送‘安装这个包’。\n"
        "当前没有发布 GitHub 地址时，Agent 需要同目录的 skillport.exe。\n"
        "exe 是安装工具，社区 ZIP 不带可执行安装器。请先核对来源和 SHA256SUMS。\n"
        "当前版本为未签名 Windows x64 程序，三端真实拖拽与调用尚待验收。\n"
        "用户无需安装 Python；源代码开发模式才需要 Python。\n", encoding="utf-8")
    if repository:
        (output / "START-HERE.md").write_text(
            f"# SkillPort {__version__}\n\n官方仓库：https://github.com/{repository}\n"
            "下载一个技能 ZIP，拖入受支持的 Agent 并发送‘安装这个包’。\n"
            "Agent 按 INSTALL.md 获取固定版本的官方安装工具，独立核对来源与摘要后安装。\n"
            "拖拽和调用的实际验收状态以仓库 docs/COMPATIBILITY.md 为准。\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text("".join(f"{sha256(p.read_bytes())}  {p.relative_to(output).as_posix()}\n" for p in sorted(output.rglob("*")) if p.is_file()), encoding="utf-8")
    return {"output": str(output), "tool_sha256": tool_hash, "published_repository": repository}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "dist"))
    parser.add_argument("--repository")
    parser.add_argument("--commit")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.repository, args.commit), ensure_ascii=False, indent=2))
    except (Invalid, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
