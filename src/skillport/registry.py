"""Small curated registry: immutable source revisions and content-addressed downloads."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener, HTTPSHandler

from .core import AGENTS, HASH, MAX_ARCHIVE, SLUG, VERSION, Invalid, inspect_package, install, read_json, require

ALLOWED_HOSTS = {"github.com", "raw.githubusercontent.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


def check_url(url):
    require(isinstance(url, str), "URL must be a string")
    try:
        value = urlsplit(url)
        port = value.port
    except ValueError as exc:
        raise Invalid(f"Invalid URL: {exc}") from exc
    require(value.scheme == "https" and value.hostname in ALLOWED_HOSTS and not value.username
            and not value.password and port in (None, 443), "Only HTTPS GitHub distribution URLs are accepted")
    return url


class GitHubRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit):
    check_url(url)
    opener = build_opener(GitHubRedirect(), HTTPSHandler())
    with opener.open(Request(url, headers={"User-Agent": "SkillPort/0.1"}), timeout=30) as response:
        check_url(response.url)
        data = response.read(limit + 1)
        require(len(data) <= limit, "Download exceeds size limit")
        return data


def validate_registry(index):
    require(isinstance(index, dict) and index.get("format") == "skillport-registry/1", "Unsupported registry format")
    packages = index.get("packages")
    require(isinstance(packages, list) and len(packages) <= 10000, "Invalid registry packages")
    seen = set()
    for entry in packages:
        require(isinstance(entry, dict), "Invalid registry entry")
        identifier, version = entry.get("id"), entry.get("version")
        require(isinstance(identifier, str) and len(identifier.split("/")) == 2 and all(SLUG.fullmatch(p) for p in identifier.split("/")), "Invalid registry id")
        require(isinstance(version, str) and VERSION.fullmatch(version), "Invalid registry version")
        require((identifier, version) not in seen, "Duplicate registry id/version")
        seen.add((identifier, version))
        for key in ("description", "author", "license"):
            require(isinstance(entry.get(key), str) and entry[key].strip(), f"Registry {key} required")
        source = entry.get("source")
        require(isinstance(source, dict) and isinstance(source.get("repository"), str)
                and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]), "Invalid source repository")
        require(isinstance(source.get("commit"), str) and re.fullmatch(r"[0-9a-f]{40}", source["commit"]), "Source must use a full commit SHA")
        archive = entry.get("archive")
        require(isinstance(archive, dict) and isinstance(archive.get("sha256"), str) and HASH.fullmatch(archive["sha256"]), "Archive SHA256 required")
        check_url(archive.get("url"))
        url = urlsplit(archive["url"])
        require(url.hostname == "github.com" and url.path.startswith(f"/{source['repository']}/releases/download/")
                and url.path.endswith(".zip") and not url.query and not url.fragment, "Archive must be a versioned GitHub release ZIP")
        compatibility = entry.get("compatibility")
        require(isinstance(compatibility, dict) and compatibility and all(a in AGENTS for a in compatibility), "Invalid registry compatibility")
        for agent, evidence in compatibility.items():
            require(isinstance(evidence, dict) and evidence.get("status") in ("declared", "verified", "not-tested", "failed"), "Invalid compatibility status")
            if evidence["status"] in ("verified", "failed"):
                for key in ("client_version", "date", "report"):
                    require(isinstance(evidence.get(key), str) and evidence[key].strip(), f"{agent}: test evidence {key} required")
                check_url(evidence["report"])
    return index


def load_registry(location=None):
    if not location:
        config = read_json(files("skillport").joinpath("data/release.json").read_bytes())
        location = config.get("registry")
        require(location, "No published registry configured; provide --registry <local index.json or official GitHub URL>")
    if str(location).startswith(("https:", "http:")):
        data = download(str(location), 5 * 1024 * 1024)
    else:
        path = Path(location)
        require(path.stat().st_size <= 5 * 1024 * 1024, "Registry exceeds 5 MiB")
        data = path.read_bytes()
    return validate_registry(read_json(data))


def search(query, location=None):
    index = load_registry(location)
    words = query.casefold().split()
    return [p for p in index["packages"] if all(w in f"{p['id']} {p['description']} {p['author']}".casefold() for w in words)]


def install_from_registry(identifier, version=None, location=None, agent=None, home=None):
    matches = [p for p in load_registry(location)["packages"] if p["id"] == identifier and (version is None or p["version"] == version)]
    require(len(matches) == 1, "Choose an exact id and version from search results")
    record = matches[0]
    with tempfile.TemporaryDirectory(prefix="skillport-download-") as temp:
        path = Path(temp) / "package.zip"
        path.write_bytes(download(record["archive"]["url"], MAX_ARCHIVE))
        manifest, _ = inspect_package(path, record["archive"]["sha256"])
        require(manifest["id"] == record["id"] and manifest["version"] == record["version"] and manifest["license"] == record["license"], "Downloaded manifest does not match registry")
        require(set(manifest["agents"]) == set(record["compatibility"]), "Declared agents differ from registry")
        return install(path, agent, home, record["archive"]["sha256"])
