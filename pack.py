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
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = ROOT / "packaging.json"
WORK_ROOT = Path(__file__).resolve().parent / ".work"


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


def first_csproj() -> Path | None:
    for path in sorted(ROOT.glob("**/*.csproj")):
        if Path("Installer") in path.parents:
            continue
        return path
    return None


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


def sanitize_identifier(text: str | None, fallback: str) -> str:
    raw = (text or "").lower()
    cleaned = "".join(ch for ch in raw if ch.isalnum())
    return cleaned or fallback


def default_cfg() -> dict:
    project = first_csproj()
    if not project:
        raise PackagingError("Could not locate a .csproj file.")

    meta = read_csproj_metadata(project)
    proj_rel = project.relative_to(ROOT).as_posix()
    proj_dir = project.parent
    ico = proj_dir / "Assets" / "app.ico"
    generated_guid = str(uuid.uuid4()).upper()
    company_slug = sanitize_identifier(meta.get("CompanyName"), "example")
    product_slug = sanitize_identifier(meta.get("ProductName") or project.stem, project.stem.lower())

    cfg = {
        "ProductName": meta.get("ProductName", project.stem),
        "CompanyName": meta.get("CompanyName", ""),
        "BundleIdentifier": f"com.{company_slug}.{product_slug}",
        "Project": proj_rel,
        "Win": {
            "Executable": f"{project.stem}.exe",
            "InnoScript": "Installer/templates/inno.iss",
            "IconIco": (ico.relative_to(ROOT).as_posix() if ico.exists() else ""),
            "GUID": f"{{{generated_guid}}}",
            "PublisherUrl": "",
        },
    }
    if "Version" in meta:
        cfg["Version"] = meta["Version"]
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
        return data, False

    cfg = default_cfg()
    with CFG_PATH.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    log(f"[config] Created default packaging.json at {CFG_PATH}")
    log("Edit the file as needed, then re-run this script.")
    return cfg, True


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


def replace_tokens(template: Path, tokens: dict[str, str], work_dir: Path) -> Path:
    text = template.read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    leftover = re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", text)
    if leftover:
        unique = ", ".join(sorted(set(leftover)))
        raise PackagingError(f"Unreplaced tokens remain in Inno template: {unique}.")
    output = work_dir / "inno_generated.iss"
    output.write_text(text, encoding="utf-8")
    return output


def package_windows(cfg: dict, publish_dir: Path, version: str) -> None:
    win_cfg = cfg.get("Win") or {}
    exe_name = win_cfg.get("Executable")
    if not exe_name:
        raise PackagingError("Win.Executable missing from packaging.json")
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

    output_base = f"{cfg['ProductName']}-{version}-win-x64"
    tokens = {
        "ProductName": cfg["ProductName"],
        "CompanyName": cfg.get("CompanyName", ""),
        "PublisherUrl": win_cfg.get("PublisherUrl", ""),
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


def main() -> None:
    cfg, created = ensure_cfg()
    if created and len(sys.argv) == 1:
        return

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    rid = "win-x64"
    publish_dir, version = publish_project(cfg, rid)
    package_windows(cfg, publish_dir, version)


if __name__ == "__main__":
    try:
        main()
    except PackagingError as err:
        log(f"ERROR: {err}")
        sys.exit(1)
    except Exception as err:  # pragma: no cover
        log(f"UNEXPECTED ERROR: {err}")
        sys.exit(1)
