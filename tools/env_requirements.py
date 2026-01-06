#!/usr/bin/env python3
"""Shared environment installer and diagnostics for simtest."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "tools" / "environment_manifest.json"
USER_BIN_DIRS = (
    Path.home() / ".local" / "bin",
    Path("/usr/local/py-utils/bin"),
)


class CheckResult:
    def __init__(self) -> None:
        self.errors: List[str] = []

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summarize(self) -> None:
        if self.ok:
            print("[doctor] environment looks good")
        else:
            print("[doctor] issues detected:")
            for item in self.errors:
                print(f"[doctor]   - {item}")


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(candidate: str) -> Path:
    return Path(os.path.expanduser(candidate)).resolve()

def extend_command_path() -> None:
    current = os.environ.get("PATH", "")
    segments = [segment for segment in current.split(os.pathsep) if segment]

    for directory in USER_BIN_DIRS:
        if not directory.exists():
            continue
        directory_str = str(directory)
        if directory_str not in segments:
            segments.insert(0, directory_str)

    os.environ["PATH"] = os.pathsep.join(segments)


def ensure_commands(names: Iterable[str], result: CheckResult) -> None:
    for name in names:
        location = shutil.which(name)
        if location:
            print(f"[doctor] command '{name}' found at {location}")
        else:
            result.add_error(f"command '{name}' not found in PATH")


def ensure_paths(paths: Iterable[str], result: CheckResult) -> None:
    for relative in paths:
        candidate = (REPO_ROOT / relative).resolve()
        if candidate.exists():
            print(f"[doctor] path '{relative}' present ({candidate})")
        else:
            result.add_error(f"required path '{relative}' missing at {candidate}")


def ensure_modules(modules: Iterable[str], result: CheckResult) -> None:
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError as error:
            result.add_error(f"python module '{module}' missing ({error})")
        else:
            print(f"[doctor] python module '{module}' import ok")


def qt_root_from_config(config: Dict[str, Any]) -> Path:
    install_dir = resolve_path(config.get("install_dir", "~/Qt"))
    version = config.get("version")
    arch = config.get("arch", "gcc_64")
    if not version:
        raise ValueError("qt.version is required in environment manifest")
    return install_dir / version / arch


def install_qt(config: Dict[str, Any]) -> None:
    if not config:
        return

    qt_root = qt_root_from_config(config)
    qt_cmake = qt_root / "bin" / "qt-cmake"

    if qt_cmake.exists():
        print(f"[install] Qt already present at {qt_root}")
        return

    host = config.get("host", "linux")
    target = config.get("target", "desktop")
    version = config.get("version")
    arch = config.get("arch", "gcc_64")
    installer_arch = config.get("installer_arch", arch)
    modules = config.get("modules") or []
    install_dir = resolve_path(config.get("install_dir", "~/Qt"))

    install_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "aqt",
        "install-qt",
        host,
        target,
        version,
        installer_arch,
        "--outputdir",
        str(install_dir),
    ]

    if modules:
        cmd.extend(["-m", *modules])

    print("[install] installing Qt toolchain via aqt")
    subprocess.run(cmd, check=True)

    if not qt_cmake.exists():
        raise RuntimeError(f"Qt installation incomplete, missing {qt_cmake}")


def ensure_qt(config: Dict[str, Any], result: CheckResult) -> None:
    if not config:
        return

    try:
        qt_root = qt_root_from_config(config)
    except ValueError as error:
        result.add_error(str(error))
        return

    qt_cmake = qt_root / "bin" / "qt-cmake"
    if qt_cmake.exists():
        print(f"[doctor] Qt toolkit available at {qt_root}")
    else:
        result.add_error(f"Qt toolkit missing (expected qt-cmake at {qt_cmake})")


def run_install(manifest: dict) -> None:
    extend_command_path()

    apt_packages = manifest.get("apt_packages", [])
    pip_packages = manifest.get("pip_packages", [])
    scripts = manifest.get("scripts", [])

    if apt_packages:
        print("[install] updating apt package index")
        subprocess.run(["sudo", "apt-get", "update"], check=True)
        print("[install] installing apt packages")
        subprocess.run(["sudo", "apt-get", "install", "-y", *apt_packages], check=True)

    if pip_packages:
        upgrade_targets: List[str] = []
        standard_targets: List[str] = []
        for package in pip_packages:
            if package.lower() == "pip":
                upgrade_targets.append(package)
            else:
                standard_targets.append(package)

        if upgrade_targets:
            print("[install] upgrading pip")
            subprocess.run(["pip3", "install", "--upgrade", *upgrade_targets], check=True)

        if standard_targets:
            print("[install] installing python packages (user scope)")
            subprocess.run(["pip3", "install", "--user", "--upgrade", *standard_targets], check=True)

    install_qt(manifest.get("qt", {}))

    for script in scripts:
        print(f"[install] running setup script: {script}")
        subprocess.run(script, shell=True, check=True, cwd=REPO_ROOT)

    print("[install] requirements install completed")


def run_check(manifest: dict) -> bool:
    extend_command_path()

    result = CheckResult()

    ensure_commands(manifest.get("commands", []), result)
    ensure_paths(manifest.get("paths", []), result)
    ensure_modules(manifest.get("python_modules", []), result)
    ensure_qt(manifest.get("qt", {}), result)

    result.summarize()
    return result.ok


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage simtest environment requirements")
    parser.add_argument(
        "action",
        choices=["install", "check"],
        help="install dependencies or validate the environment",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to environment manifest JSON",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    manifest = load_manifest(args.manifest)

    if args.action == "install":
        run_install(manifest)
        return 0

    if args.action == "check":
        ok = run_check(manifest)
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
