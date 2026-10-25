import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from skillport import core, registry
from skillport.cli import main

ROOT = Path(__file__).resolve().parents[1]


class SkillPortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillport-test-")
        self.root = Path(self.temp.name)
        self.bundle = self.root / "starter.zip"
        core.pack(ROOT / "examples/pack-starter.json", self.bundle)

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, mutate):
        with zipfile.ZipFile(self.bundle) as archive:
            data = {i.filename: archive.read(i) for i in archive.infolist()}
        mutate(data)
        target = self.root / "changed.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, value in data.items():
                if isinstance(name, zipfile.ZipInfo):
                    archive.writestr(name, value)
                else:
                    archive.writestr(name, value)
        return target

    def test_single_bundle_manager_and_unicode_home(self):
        for kind, count in (("manager", 1), ("brief", 2), ("starter", 3)):
            with self.subTest(kind=kind):
                package = self.root / f"matrix-{kind}.zip"
                core.pack(ROOT / f"examples/pack-{kind}.json", package)
                for agent, folder in (("claude-code", ".claude"), ("codex", ".agents"), ("hermes", ".hermes")):
                    home = self.root / f"中文 空格 {kind} {agent}"
                    with patch.dict(os.environ, {}, clear=True):
                        result = core.install(package, agent, home)
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(len(result["results"]), count)
                    self.assertEqual(result["scope"], "isolated-test")
                    self.assertTrue((home / folder / "skills/skillport/SKILL.md").is_file())
                    self.assertTrue(all(r["host_recognized"] == "unverified" for r in result["results"]))

    def test_idempotent_does_not_overwrite_and_continues_bundle(self):
        home = self.root / "home"
        self.assertTrue(core.install(self.bundle, "codex", home)["ok"])
        self.assertTrue(all(r["files"] == "unchanged" for r in core.install(self.bundle, "codex", home)["results"]))
        target = home / ".agents/skills/skillport-brief/SKILL.md"
        target.write_text("user edits", encoding="utf-8")
        result = core.install(self.bundle, "codex", home)
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"][1]["files"], "conflict")
        self.assertEqual(result["results"][2]["files"], "unchanged")
        self.assertEqual(target.read_text(encoding="utf-8"), "user edits")

    def test_install_failure_cleans_stage_and_continues(self):
        real_rename = os.rename
        def fail_one(source, destination):
            if Path(destination).name == "skillport-brief":
                raise PermissionError("simulated disk/write failure")
            return real_rename(source, destination)
        with patch("skillport.core.os.rename", side_effect=fail_one):
            result = core.install(self.bundle, "codex", self.root / "home")
        target = self.root / "home/.agents/skills"
        self.assertFalse(result["ok"])
        self.assertFalse((target / "skillport-brief").exists())
        self.assertTrue((target / "skillport-checklist/SKILL.md").is_file())
        self.assertEqual(list(target.glob(".skillport-stage-*")), [])

    def test_hash_mismatch_rejected_before_any_write(self):
        path = self.rewrite(lambda data: data.__setitem__("skills/skillport-brief/SKILL.md", b"tampered"))
        home = self.root / "home"
        with self.assertRaises(core.Invalid):
            core.install(path, "codex", home)
        self.assertFalse(home.exists())
        with self.assertRaises(core.Invalid):
            core.inspect_package(self.bundle, "0" * 64)

    def test_unsafe_archive_paths(self):
        for name in ("../outside", "/absolute", "C:/outside", "skills\\bad", "skills/CON.txt", "skills/trailing.", "skills/a:ads", "skills/LPT¹.log", "skills//double"):
            with self.subTest(name=name):
                bad = self.rewrite(lambda data: data.__setitem__(name, b"bad"))
                with self.assertRaises(core.Invalid):
                    core.inspect_package(bad)

    def test_links_special_files_and_duplicates(self):
        link = zipfile.ZipInfo("skills/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(core.Invalid):
            core.inspect_package(self.rewrite(lambda data: data.__setitem__(link, b"outside")))
        with self.assertRaises(core.Invalid):
            core.inspect_package(self.rewrite(lambda data: data.__setitem__("MANIFEST.JSON", data["manifest.json"])))
        path = self.root / "duplicate.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("same", b"a")
            with contextlib.redirect_stderr(io.StringIO()):
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    archive.writestr("same", b"b")
        with self.assertRaises(core.Invalid):
            core.inspect_package(path)

    def test_limits_crc_and_malformed_json(self):
        with patch.object(core, "MAX_ENTRIES", 1):
            with self.assertRaises(core.Invalid):
                core.inspect_package(self.bundle)
        with patch.object(core, "MAX_TOTAL", 10):
            with self.assertRaises(core.Invalid):
                core.inspect_package(self.bundle)
        with patch.object(core, "MAX_ARCHIVE", 10):
            with self.assertRaises(core.Invalid):
                core.inspect_package(self.bundle)
        with self.assertRaises(core.Invalid):
            core.inspect_package(self.rewrite(lambda data: data.__setitem__("skills/bomb", b"0" * (2 * 1024 * 1024))))
        self.bundle.write_bytes(b"not a zip")
        with self.assertRaises(core.Invalid):
            core.inspect_package(self.bundle)
        with self.assertRaises(core.Invalid):
            core.read_json(b'{"x":1,"x":2}')

    def test_damaged_crc_rejected(self):
        path = self.root / "crc.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", b"crc-target")
        data = path.read_bytes()
        data = data.replace(b"crc-target", b"crc-broken", 1)
        path.write_bytes(data)
        with self.assertRaises(core.Invalid):
            core.inspect_package(path)
        compressed = self.root / "compressed-corrupt.zip"
        with zipfile.ZipFile(compressed, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", b"some compressed data" * 10)
        data = bytearray(compressed.read_bytes())
        with zipfile.ZipFile(compressed) as archive:
            info = archive.infolist()[0]
            start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
            data[start:start + info.compress_size] = b"\xff" * info.compress_size
        compressed.write_bytes(data)
        with self.assertRaises(core.Invalid):
            core.inspect_package(compressed)

    def test_deterministic_package_and_refuses_output_overwrite(self):
        second = self.root / "second.zip"
        core.pack(ROOT / "examples/pack-starter.json", second)
        self.assertEqual(self.bundle.read_bytes(), second.read_bytes())
        with self.assertRaises(core.Invalid):
            core.pack(ROOT / "examples/pack-starter.json", second)

    def test_reparse_points_are_rejected(self):
        from types import SimpleNamespace
        fake = SimpleNamespace(lstat=lambda: SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400))
        self.assertTrue(core.is_link(fake))
        home = self.root / "home"
        with patch("skillport.core.is_link", return_value=True):
            with self.assertRaises(core.Invalid):
                core.install(self.bundle, "codex", home)
        self.assertFalse(home.exists())

    def test_malformed_manifest_types_rejected(self):
        for field, value in (("agents", [{}]), ("skills", "wrong"), ("version", 1), ("id", [])):
            def change(data):
                manifest = core.read_json(data["manifest.json"])
                manifest[field] = value
                data["manifest.json"] = core.json_bytes(manifest)
            with self.subTest(field=field), self.assertRaises(core.Invalid):
                core.inspect_package(self.rewrite(change))

    def test_missing_reference_yaml_metadata_and_side_effect_free_scripts(self):
        files = {"SKILL.md": b"---\nname: test\ndescription: valid\n---\n[missing](references/no.md)"}
        with self.assertRaises(core.Invalid):
            core.validate_skill("test", files)
        for front in ("name: test\nname: test\ndescription: valid", "name: test\ndescription: &x valid\nmetadata: *x", "name: other\ndescription: valid", "name: test\ndescription: 42"):
            with self.assertRaises(core.Invalid):
                core.validate_skill("test", {"SKILL.md": f"---\n{front}\n---\n".encode()})
        directory = self.root / "test"
        directory.mkdir()
        (directory / "SKILL.md").write_text("---\nname: test\ndescription: valid\n---\n", encoding="utf-8")
        marker = self.root / "SHOULD_NOT_EXIST"
        (directory / "evil.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')", encoding="utf-8")
        config = self.root / "pack.json"
        config.write_bytes(core.json_bytes({"id": "test/package", "version": "1.0.0", "license": "MIT", "agents": ["codex"], "skills": [{"path": "test", "license": "MIT"}]}))
        package = self.root / "script.zip"
        core.pack(config, package)
        core.install(package, "codex", self.root / "home")
        self.assertFalse(marker.exists())

    def test_credentials_caches_omitted_and_reported(self):
        skill = self.root / "test"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: test\ndescription: valid\n---\n", encoding="utf-8")
        for name in (".env", ".env.production", "private.pem", "credentials.json"):
            (skill / name).write_text("secret", encoding="utf-8")
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__/evil.pyc").write_bytes(b"cache")
        files, omitted = core.collect_skill(skill)
        self.assertEqual(set(files), {"SKILL.md"})
        self.assertEqual(len(omitted), 5)

    def test_target_requires_reliable_identity_and_rejects_hermes_profiles(self):
        with self.assertRaises(core.Invalid):
            core.resolve_target(home=self.root, environ={})
        with self.assertRaises(core.Invalid):
            core.resolve_target(home=self.root, environ={"CODEX_THREAD_ID": "id", "CLAUDECODE": "1"})
        agent, target = core.resolve_target(home=self.root, environ={"CODEX_THREAD_ID": "id"})
        self.assertEqual(agent, "codex")
        self.assertEqual(target, self.root / ".agents/skills")
        with self.assertRaises(core.Invalid):
            core.resolve_target("hermes", self.root, {"HERMES_PROFILE": "work"})

    def test_dependency_is_pending_not_installed(self):
        def change(data):
            manifest = core.read_json(data["manifest.json"])
            manifest["skills"][0]["dependencies"] = ["An external tool; configure separately"]
            data["manifest.json"] = core.json_bytes(manifest)
        result = core.install(self.rewrite(change), "codex", self.root / "home")
        self.assertEqual(result["results"][1]["dependencies"], "pending")
        self.assertTrue(result["ok"])

    def test_dev_manager_is_runnable_and_self_contained(self):
        result = core.install(self.bundle, "codex", self.root / "home")
        tool = Path(result["results"][0]["path"]) / "bin/skillport.pyz"
        run = subprocess.run([sys.executable, str(tool), "inspect", str(self.bundle)], capture_output=True, text=True, encoding="utf-8", cwd=self.root)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["valid"])
        installed = subprocess.run([sys.executable, str(tool), "install", str(self.bundle), "--agent", "codex", "--home", str(self.root / "second-home")], capture_output=True, encoding="utf-8", cwd=self.root)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertTrue(json.loads(installed.stdout)["ok"])

    def test_cli_json_is_utf8_even_in_legacy_windows_encoding(self):
        env = {**os.environ, "PYTHONIOENCODING": "gbk"}
        result = subprocess.run([sys.executable, "-m", "skillport", "install", str(self.bundle), "--agent", "codex", "--home", str(self.root / "中文 路径")], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout.decode("utf-8"))["ok"])

    def record(self):
        return {"id": "skillport/starter", "version": "0.1.0", "description": "中文 示例", "author": "example", "license": "MIT",
                "source": {"repository": "example/skillport", "commit": "a" * 40},
                "archive": {"url": "https://github.com/example/skillport/releases/download/v0.1.0/starter.zip", "sha256": core.sha256(self.bundle.read_bytes())},
                "compatibility": {a: {"status": "declared"} for a in core.AGENTS}}

    def test_registry_search_install_hash_identity_and_evidence(self):
        record = self.record()
        index = self.root / "index.json"
        index.write_bytes(core.json_bytes({"format": "skillport-registry/1", "packages": [record]}))
        self.assertEqual(len(registry.search("中文", index)), 1)
        with patch("skillport.registry.download", return_value=self.bundle.read_bytes()):
            result = registry.install_from_registry(record["id"], "0.1.0", index, "codex", self.root / "home")
        self.assertTrue(result["ok"])
        record["compatibility"]["codex"] = {"status": "verified"}
        with self.assertRaises(core.Invalid):
            registry.validate_registry({"format": "skillport-registry/1", "packages": [record]})
        for url in ("http://github.com/a/b", "https://evil.example/test", "https://github.com@evil.example/test", "file:///etc/passwd"):
            with self.assertRaises(core.Invalid):
                registry.check_url(url)

    def test_cli_reports_error_and_conflict_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["inspect", str(self.root / "absent.zip")]), 2)
            self.assertEqual(main(["install", str(self.bundle), "--agent", "codex", "--home", str(self.root / "home")]), 0)
            target = self.root / "home/.agents/skills/skillport-brief/SKILL.md"
            target.write_text("edited", encoding="utf-8")
            self.assertEqual(main(["install", str(self.bundle), "--agent", "codex", "--home", str(self.root / "home")]), 1)


if __name__ == "__main__":
    unittest.main()
