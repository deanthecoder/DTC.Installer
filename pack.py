#!/usr/bin/env python3
# Created by DeanTheCoder - https://github.com/DeanTheCoder/DTC.Installer

"""
Reusable packaging helper for .NET projects.

Currently drives the Windows/Inno Setup packaging flow. Additional
platform support can be layered in later without impacting consumers.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import configparser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = ROOT / "packaging.json"
WORK_ROOT = Path(__file__).resolve().parent / ".work"
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = os.name == "nt"
DEFAULT_VERSION = "0.1"


def prefs_path() -> Path:
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / "Preferences" / "com.deanthecoder.installer.json"
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home())) / "com.deanthecoder.installer.json"
    return Path.home() / ".config" / "com.deanthecoder.installer.json"


class PackagingError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def sh(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """Run a subprocess and return stdout."""
    log(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if check and proc.returncode != 0:
        raise PackagingError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.stdout or ""


def load_preferences() -> dict:
    path = prefs_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_preferences(prefs: dict) -> None:
    path = prefs_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        log(f"[warn] Could not write preferences to {path}: {exc}")


def first_csproj() -> Path | None:
    projects = [path for path in ROOT.glob("**/*.csproj")]
    if not projects:
        return None

    root_name = ROOT.name.lower()
    name_matches = [path for path in projects if path.stem.lower() == root_name]
    if name_matches:
        projects = name_matches

    def depth(path: Path) -> int:
        try:
            return len(path.relative_to(ROOT).parts)
        except ValueError:
            return len(path.parts)
    min_depth = min(depth(path) for path in projects)
    shallow = [path for path in projects if depth(path) == min_depth]
    return sorted(shallow)[0]


def read_csproj_metadata(project: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        tree = ET.parse(project)
    except ET.ParseError:
        return meta

    root = tree.getroot()
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]  # strip XML namespace if present
        text = (node.text or "").strip()
        if not text:
            continue
        if tag == "Company":
            meta["CompanyName"] = text
        elif tag in {"ApplicationTitle", "AssemblyName"}:
            meta.setdefault("ProductName", text)
        elif tag == "RootNamespace":
            meta.setdefault("RootNamespace", text)
        elif tag == "Version":
            meta["Version"] = text
    if "ProductName" not in meta:
        meta["ProductName"] = project.stem
    return meta


def validate_version(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackagingError("Version must be a non-empty string.")
    value = value.strip()
    if not re.fullmatch(r"\d+\.\d+", value):
        raise PackagingError("Version must use major.minor format (e.g. 1.2).")
    return value


def sanitize_identifier(text: str | None, fallback: str) -> str:
    raw = (text or "").lower()
    cleaned = "".join(ch for ch in raw if ch.isalnum())
    return cleaned or fallback


def get_prefix_map(prefs: dict) -> dict:
    mapping = prefs.get("BundleIdentifierPrefixMap")
    return mapping if isinstance(mapping, dict) else {}


def git_dir() -> Path | None:
    git_path = ROOT / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        try:
            text = git_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir:"):
            rel = text.split("gitdir:", 1)[1].strip()
            git_dir_path = (ROOT / rel).resolve()
            return git_dir_path if git_dir_path.exists() else None
    return None


def git_remote_url() -> str:
    git_root = git_dir()
    if not git_root:
        return ""
    config_path = git_root / "config"
    if not config_path.exists():
        return ""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(config_path, encoding="utf-8")
    except (OSError, configparser.Error):
        return ""
    section = 'remote "origin"'
    if not parser.has_section(section):
        return ""
    return (parser.get(section, "url", fallback="") or "").strip()


def publisher_url_from_remote(remote: str) -> str:
    if not remote:
        return ""
    remote = remote.strip()
    match = re.match(r"^https?://([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if not match:
        match = re.match(r"^git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if not match:
        return ""
    host, owner, _repo = match.groups()
    return f"https://{host}/{owner}"


def default_publisher_url() -> str:
    return publisher_url_from_remote(git_remote_url())


def normalize_bundle_prefix(prefix: str | None) -> str | None:
    if not prefix:
        return None
    prefix = str(prefix).strip()
    if not prefix:
        return None
    if not prefix.endswith("."):
        prefix += "."
    return prefix


def extract_bundle_prefix(bundle_id: str | None) -> str | None:
    if not bundle_id:
        return None
    parts = [part for part in str(bundle_id).strip().split(".") if part]
    if len(parts) < 3:
        return None
    return normalize_bundle_prefix(".".join(parts[:-1]))


def auto_bundle_prefix(cfg: dict) -> str:
    company_slug = sanitize_identifier(cfg.get("CompanyName"), "example")
    return normalize_bundle_prefix(f"com.{company_slug}") or "com.example."


def preferred_bundle_prefix(prefs: dict, auto_prefix: str) -> str | None:
    mapping = get_prefix_map(prefs)
    if auto_prefix in mapping:
        return normalize_bundle_prefix(mapping.get(auto_prefix))
    legacy = prefs.get("BundleIdentifierPrefix")
    return normalize_bundle_prefix(legacy)


def find_first_icon(project_dir: Path, pattern: str) -> Path | None:
    if not project_dir or not project_dir.exists():
        return None
    matches = []
    for path in project_dir.rglob(pattern):
        if not path.is_file():
            continue
        parts = [part.lower() for part in path.parts]
        if "bin" in parts or "obj" in parts:
            continue
        matches.append(path)
    if not matches:
        return None
    first = sorted(matches)[0]
    return first.resolve()


def remember_bundle_prefix(cfg: dict) -> None:
    auto_prefix = auto_bundle_prefix(cfg)
    actual_prefix = extract_bundle_prefix(cfg.get("BundleIdentifier"))
    if not actual_prefix:
        return
    prefs = load_preferences()
    mapping = get_prefix_map(prefs)
    if mapping.get(auto_prefix) == actual_prefix:
        return
    mapping[auto_prefix] = actual_prefix
    prefs["BundleIdentifierPrefixMap"] = mapping
    save_preferences(prefs)


def ensure_bundle_identifier(cfg: dict, updates: list[str]) -> None:
    if cfg.get("BundleIdentifier"):
        return

    project_rel = cfg.get("Project")
    default_product = ""
    if project_rel:
        default_product = Path(project_rel).stem
    else:
        project = first_csproj()
        if project:
            default_product = project.stem
    if not default_product:
        default_product = "app"

    base_product = cfg.get("ProductName") or default_product
    prefs = load_preferences()
    auto_prefix = auto_bundle_prefix(cfg)
    preferred_prefix = preferred_bundle_prefix(prefs, auto_prefix)
    product_slug = sanitize_identifier(base_product, default_product.lower())
    if preferred_prefix:
        cfg["BundleIdentifier"] = f"{preferred_prefix}{product_slug}"
    else:
        cfg["BundleIdentifier"] = f"{auto_prefix}{product_slug}"
    updates.append("Added default BundleIdentifier")


def mac_defaults(cfg: dict) -> dict:
    project_rel = cfg.get("Project", "")
    project_path: Path | None = None
    if project_rel:
        project_path = (ROOT / project_rel).resolve()
    else:
        project_path = first_csproj()
        if project_path:
            try:
                cfg["Project"] = project_path.relative_to(ROOT).as_posix()
            except ValueError:
                cfg["Project"] = project_path.as_posix()
    exe_name = cfg.get("Executable") or Path(cfg.get("Project", "")).stem or (cfg.get("ProductName") or "app")

    icon_rel = ""
    if project_path and project_path.exists():
        icon_path = project_path.parent / "Assets" / "app.icns"
        if icon_path.exists():
            try:
                icon_rel = icon_path.relative_to(ROOT).as_posix()
            except ValueError:
                icon_rel = icon_path.as_posix()
        else:
            fallback_icon = find_first_icon(project_path.parent, "*.icns")
            if fallback_icon:
                try:
                    icon_rel = fallback_icon.relative_to(ROOT).as_posix()
                except ValueError:
                    icon_rel = fallback_icon.as_posix()

    return {
        "RuntimeIdentifiers": ["osx-arm64", "osx-x64"],
        "IconIcns": icon_rel,
        "InfoPlist": "Installer/templates/Info.plist",
    }


def ensure_mac_section(cfg: dict, updates: list[str]) -> None:
    mac_cfg = cfg.get("Mac")
    if mac_cfg is None and "Mac" in cfg:
        return
    if "Mac" not in cfg:
        cfg["Mac"] = mac_defaults(cfg)
        updates.append("Added default Mac packaging section")
        return

    updated = False
    mac_cfg = cfg["Mac"] or {}
    if "RuntimeIdentifiers" not in mac_cfg or not mac_cfg.get("RuntimeIdentifiers"):
        mac_cfg["RuntimeIdentifiers"] = ["osx-arm64", "osx-x64"]
        updated = True
    if not mac_cfg.get("InfoPlist"):
        mac_cfg["InfoPlist"] = "Installer/templates/Info.plist"
        updated = True
    if updated:
        cfg["Mac"] = mac_cfg
        updates.append("Normalised Mac packaging settings")


def ensure_version(cfg: dict, updates: list[str]) -> None:
    version = cfg.get("Version")
    if version:
        cfg["Version"] = validate_version(str(version))
        return

    project_rel = cfg.get("Project")
    project_path = (ROOT / project_rel).resolve() if project_rel else first_csproj()
    if project_path and project_path.exists():
        meta = read_csproj_metadata(project_path)
        existing = meta.get("Version")
        if existing:
            try:
                cfg["Version"] = validate_version(existing)
                updates.append("Added Version from project metadata")
                return
            except PackagingError:
                pass

    cfg["Version"] = DEFAULT_VERSION
    updates.append("Added default Version")


def ensure_publisher_url(cfg: dict, updates: list[str]) -> None:
    if cfg.get("PublisherUrl"):
        return
    publisher_url = default_publisher_url()
    if not publisher_url:
        return
    cfg["PublisherUrl"] = publisher_url
    updates.append("Added default PublisherUrl from git remote")


def default_cfg() -> dict:
    project = first_csproj()
    if not project:
        raise PackagingError("Could not locate a .csproj file.")

    meta = read_csproj_metadata(project)
    proj_rel = project.relative_to(ROOT).as_posix()
    proj_dir = project.parent
    ico = proj_dir / "Assets" / "app.ico"
    icns = proj_dir / "Assets" / "app.icns"
    icon_ico = ico
    icon_icns = icns
    if not icon_ico.exists():
        fallback_ico = find_first_icon(proj_dir, "*.ico")
        if fallback_ico:
            icon_ico = fallback_ico
    if not icon_icns.exists():
        fallback_icns = find_first_icon(proj_dir, "*.icns")
        if fallback_icns:
            icon_icns = fallback_icns
    generated_guid = str(uuid.uuid4()).upper()
    company_slug = sanitize_identifier(meta.get("CompanyName"), "example")
    product_slug = sanitize_identifier(meta.get("ProductName") or project.stem, project.stem.lower())
    auto_prefix = normalize_bundle_prefix(f"com.{company_slug}") or "com.example."
    preferred_prefix = preferred_bundle_prefix(load_preferences(), auto_prefix)
    if preferred_prefix:
        bundle_id = f"{preferred_prefix}{product_slug}"
    else:
        bundle_id = f"{auto_prefix}{product_slug}"
    publisher_url = default_publisher_url()

    cfg = {
        "ProductName": meta.get("ProductName", project.stem),
        "CompanyName": meta.get("CompanyName", ""),
        "PublisherUrl": publisher_url,
        "BundleIdentifier": bundle_id,
        "Executable": project.stem,
        "Project": proj_rel,
        "Version": validate_version(meta.get("Version", DEFAULT_VERSION)),
        "Win": {
            "InnoScript": "Installer/templates/inno.iss",
            "IconIco": (icon_ico.relative_to(ROOT).as_posix() if icon_ico.exists() else ""),
            "GUID": f"{{{generated_guid}}}",
            "RuntimeIdentifier": "win-x64",
        },
        "Mac": {
            "RuntimeIdentifiers": ["osx-arm64", "osx-x64"],
            "IconIcns": (icon_icns.relative_to(ROOT).as_posix() if icon_icns.exists() else ""),
            "InfoPlist": "Installer/templates/Info.plist",
        },
    }
    return cfg


def ensure_cfg() -> tuple[dict, bool]:
    if CFG_PATH.exists():
        with CFG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                log("[config] Normalised legacy packaging.json structure.")
                data = data[0]
                with CFG_PATH.open("w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                    fh.write("\n")
            else:
                raise PackagingError("Unexpected packaging.json structure.")
        updates: list[str] = []
        ensure_bundle_identifier(data, updates)
        ensure_mac_section(data, updates)
        ensure_version(data, updates)
        ensure_publisher_url(data, updates)
        remember_bundle_prefix(data)
        if updates:
            with CFG_PATH.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            log("[config] Updated packaging.json:")
            for item in updates:
                log(f"         - {item}")
        return data, False

    cfg = default_cfg()
    remember_bundle_prefix(cfg)
    with CFG_PATH.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    log(f"[config] Created default packaging.json at {CFG_PATH}")
    log("Edit the file as needed, then re-run this script.")
    return cfg, True


def update_project_version(cfg: dict) -> None:
    project_rel = cfg.get("Project")
    if not project_rel:
        return
    project = (ROOT / project_rel).resolve()
    if not project.exists():
        raise PackagingError(f"Project file not found: {project}")

    version = validate_version(str(cfg.get("Version", DEFAULT_VERSION)))
    raw_bytes = project.read_bytes()
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    text = raw_bytes.decode("utf-8-sig")

    version_pattern = r"<Version>.*?</Version>"
    if re.search(version_pattern, text, flags=re.DOTALL):
        updated = re.sub(version_pattern, f"<Version>{version}</Version>", text, count=1, flags=re.DOTALL)
    else:
        group_match = re.search(r"(<PropertyGroup>[\s\S]*?</PropertyGroup>)", text)
        if not group_match:
            raise PackagingError("Project file has no <PropertyGroup> to set Version.")
        group_text = group_match.group(1)
        insert_line = f"        <Version>{version}</Version>\n"
        tf_match = re.search(r"(\s*<TargetFrameworks?>.*?</TargetFrameworks?>\s*\n?)", group_text)
        if tf_match:
            insert_at = tf_match.end(1)
            new_group = group_text[:insert_at] + insert_line + group_text[insert_at:]
        else:
            close_idx = group_text.rfind("</PropertyGroup>")
            new_group = group_text[:close_idx] + insert_line + group_text[close_idx:]
        updated = text[:group_match.start(1)] + new_group + text[group_match.end(1):]

    if updated == text:
        return

    if has_bom:
        project.write_text("\ufeff" + updated, encoding="utf-8")
    else:
        project.write_text(updated, encoding="utf-8")


def git_version() -> str:
    try:
        out = sh(["git", "describe", "--tags", "--dirty", "--always"], check=True)
        return out.strip()
    except PackagingError:
        return "0.0.0"


def publish_project(cfg: dict, rid: str) -> tuple[Path, str]:
    project = (ROOT / cfg["Project"]).resolve()
    if not project.exists():
        raise PackagingError(f"Project file not found: {project}")

    publish_dir = WORK_ROOT / "publish" / rid
    if publish_dir.exists():
        shutil.rmtree(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)

    args = cfg.get("PublishArgs")
    if args is None:
        args = ["-c", "Release"]
    elif isinstance(args, str):
        args = [args]
    cmd = [
        "dotnet",
        "publish",
        str(project),
        "-r",
        rid,
        "-o",
        str(publish_dir),
    ]
    cmd.extend(args)
    sh(cmd)
    for pdb in publish_dir.rglob("*.pdb"):
        try:
            pdb.unlink()
        except OSError:
            pass
    version = cfg.get("Version") or git_version()
    return publish_dir, version


def locate_inno_compiler(win_cfg: dict) -> str:
    preferred = win_cfg.get("Compiler", "iscc")
    candidates: list[str] = []

    path_candidate = shutil.which(preferred)
    if path_candidate:
        candidates.append(path_candidate)

    explicit = Path(preferred)
    if explicit.exists():
        candidates.append(str(explicit))

    known_locations = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for loc in known_locations:
        if loc.exists():
            candidates.append(str(loc))

    if candidates:
        return candidates[0]

    raise PackagingError(
        "Inno Setup compiler not found. Install Inno Setup 6 or set "
        "Win.Compiler to the ISCC.exe path."
    )


def replace_tokens(template: Path, tokens: dict[str, str], work_dir: Path, output_name: str = "inno_generated.iss") -> Path:
    text = template.read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    leftover = re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", text)
    if leftover:
        unique = ", ".join(sorted(set(leftover)))
        raise PackagingError(f"Unreplaced tokens remain in Inno template: {unique}.")
    output = work_dir / output_name
    output.write_text(text, encoding="utf-8")
    return output


def package_windows(cfg: dict, publish_dir: Path, version: str, rid: str) -> None:
    win_cfg = cfg.get("Win") or {}
    exe_name = win_cfg.get("Executable") or cfg.get("Executable")
    if not exe_name:
        raise PackagingError("Win.Executable missing from packaging.json")
    if not exe_name.lower().endswith(".exe"):
        exe_name = f"{exe_name}.exe"
    exe_path = publish_dir / exe_name
    if not exe_path.exists():
        raise PackagingError(f"Published executable not found: {exe_path}")

    template_path = ROOT / win_cfg.get("InnoScript", "")
    if not template_path.exists():
        raise PackagingError(f"Inno script template missing: {template_path}")

    icon_path = ROOT / win_cfg.get("IconIco", "")
    if win_cfg.get("IconIco") and not icon_path.exists():
        log(f"[warn] Windows icon not found at {icon_path} - installer will use default.")

    app_id = win_cfg.get("GUID")
    if not app_id:
        core = str(uuid.uuid4()).upper()
        log("[win] Win.GUID missing in packaging.json; generated a temporary value for this build.")
    else:
        core = str(app_id).strip().strip("{}").upper()
    app_id = f"{{{{{core}}}}}"

    dist_dir = ROOT / "dist" / "win"
    dist_dir.mkdir(parents=True, exist_ok=True)

    work_dir = WORK_ROOT / "windows"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    output_base = f"{cfg['ProductName']}-{version}-{rid}"
    tokens = {
        "ProductName": cfg["ProductName"],
        "CompanyName": cfg.get("CompanyName", ""),
        "PublisherUrl": win_cfg.get("PublisherUrl") or cfg.get("PublisherUrl", ""),
        "Version": version,
        "Executable": exe_name,
        "AppId": app_id,
        "SourceDir": str(publish_dir),
        "OutputDir": str(dist_dir),
        "OutputBase": output_base,
        "SetupIconFile": str(icon_path) if icon_path.exists() else "",
    }

    work_iss = replace_tokens(template_path, tokens, work_dir)
    compiler = locate_inno_compiler(win_cfg)
    try:
        sh([compiler, str(work_iss.resolve())])
    except FileNotFoundError as exc:  # pragma: no cover (safety)
        raise PackagingError(
            "Inno Setup compiler not found on PATH. Install Inno Setup and "
            "ensure 'iscc' is available."
        ) from exc

    log(f"[win] Installer written to {dist_dir}")


def copy_publish_tree(src: Path, dest: Path) -> None:
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target)


def ensure_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as exc:
        raise PackagingError(f"Expected executable not found: {path}") from exc
    if mode & stat.S_IXUSR:
        return
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def normalize_runtime_identifiers(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise PackagingError("Runtime identifiers must be a string or list of strings.")


def package_macos(cfg: dict, publish_dir: Path, version: str, rid: str) -> None:
    if not IS_MACOS:
        raise PackagingError("macOS packaging requires running on macOS.")

    mac_cfg = cfg.get("Mac") or {}
    exe_name = mac_cfg.get("Executable") or cfg.get("Executable") or Path(cfg["Project"]).stem
    if exe_name.lower().endswith(".exe"):
        exe_name = exe_name[:-4]
    app_name = mac_cfg.get("AppName") or cfg["ProductName"]
    bundle_identifier = mac_cfg.get("BundleIdentifier") or cfg.get("BundleIdentifier")
    if not bundle_identifier:
        raise PackagingError("Bundle identifier missing; set BundleIdentifier or Mac.BundleIdentifier.")

    info_plist_template = ROOT / mac_cfg.get("InfoPlist", "Installer/templates/Info.plist")
    if not info_plist_template.exists():
        raise PackagingError(f"Info.plist template missing: {info_plist_template}")

    icon_rel = mac_cfg.get("IconIcns", "")
    icon_path = ROOT / icon_rel if icon_rel else None
    default_icon_path: Path | None = None
    project_rel = cfg.get("Project")
    if project_rel:
        project_path = (ROOT / project_rel).resolve()
        default_icon_path = project_path.parent / "Assets" / "app.icns"

    dist_dir = ROOT / "dist" / "mac"
    dist_dir.mkdir(parents=True, exist_ok=True)

    work_dir = WORK_ROOT / f"mac-{rid}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    bundle_root = work_dir / f"{app_name}.app"
    contents_dir = bundle_root / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    copy_publish_tree(publish_dir, macos_dir)

    exe_path = macos_dir / exe_name
    if not exe_path.exists():
        raise PackagingError(
            f"Published executable not found for macOS build: {exe_path}. "
            "Ensure PublishArgs enable a self-contained build."
        )
    ensure_executable(exe_path)

    icon_token = ""
    icon_candidates: list[Path] = []
    if icon_path:
        icon_candidates.append(icon_path)
    if default_icon_path:
        icon_candidates.append(default_icon_path)

    icon_source: Path | None = None
    for candidate in icon_candidates:
        if candidate and candidate.exists():
            icon_source = candidate
            break

    if icon_source:
        icon_dest = resources_dir / icon_source.name
        shutil.copy2(icon_source, icon_dest)
        icon_token = icon_dest.stem
    else:
        if icon_path:
            log(
                f"[warn] macOS icon not found at {icon_path} - app bundle will use default."
            )
        elif default_icon_path:
            log(
                f"[warn] macOS icon not found at {default_icon_path} - add an .icns file or set Mac.IconIcns."
            )

    tokens = {
        "ProductName": cfg["ProductName"],
        "BundleIdentifier": bundle_identifier,
        "Version": version,
        "Executable": exe_name,
        "IconFile": icon_token,
        "Category": mac_cfg.get("Category", ""),
        "MinimumSystemVersion": mac_cfg.get("MinimumSystemVersion", "11.0"),
        "Copyright": cfg.get("CompanyName", ""),
        "PublisherUrl": mac_cfg.get("PublisherUrl") or cfg.get("PublisherUrl", ""),
    }

    info_plist_generated = replace_tokens(info_plist_template, tokens, work_dir, output_name="Info.plist")
    contents_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(info_plist_generated, contents_dir / "Info.plist")
    (contents_dir / "PkgInfo").write_text("APPL????", encoding="utf-8")

    staging_dir = work_dir / "dmg"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle_root, staging_dir / bundle_root.name)

    applications_link = staging_dir / "Applications"
    if applications_link.exists() or applications_link.is_symlink():
        applications_link.unlink()
    applications_link.symlink_to("/Applications")

    volname = mac_cfg.get("VolumeName") or app_name
    dmg_name = f"{cfg['ProductName']}-{version}-{rid}.dmg"
    dmg_path = dist_dir / dmg_name
    if dmg_path.exists():
        dmg_path.unlink()

    sh(
        [
            "hdiutil",
            "create",
            "-fs",
            "HFS+",
            "-srcfolder",
            str(staging_dir),
            "-volname",
            volname,
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ]
    )

    log(f"[mac] Disk image ({rid}) written to {dmg_path}")


def main() -> None:
    cfg, created = ensure_cfg()
    update_project_version(cfg)
    if created and len(sys.argv) == 1:
        return

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    any_packaged = False

    win_cfg = cfg.get("Win")
    if win_cfg and IS_WINDOWS:
        win_rid = win_cfg.get("RuntimeIdentifier", "win-x64")
        publish_dir, version = publish_project(cfg, win_rid)
        package_windows(cfg, publish_dir, version, win_rid)
        any_packaged = True

    mac_cfg = cfg.get("Mac")
    if mac_cfg:
        if not IS_MACOS:
            log("[mac] Skipping macOS packaging; requires running on macOS.")
        else:
            runtime_ids = mac_cfg.get("RuntimeIdentifiers", ["osx-arm64", "osx-x64"])
            runtime_ids = normalize_runtime_identifiers(runtime_ids)
            if not runtime_ids:
                raise PackagingError("Mac.RuntimeIdentifiers is empty.")
            for mac_rid in runtime_ids:
                publish_dir, version = publish_project(cfg, mac_rid)
                package_macos(cfg, publish_dir, version, mac_rid)
            any_packaged = True

    if not any_packaged:
        log("No packaging targets were executed. Enable Win or Mac sections in packaging.json.")


if __name__ == "__main__":
    try:
        main()
    except PackagingError as err:
        log(f"ERROR: {err}")
        sys.exit(1)
    except Exception as err:  # pragma: no cover
        log(f"UNEXPECTED ERROR: {err}")
        sys.exit(1)
