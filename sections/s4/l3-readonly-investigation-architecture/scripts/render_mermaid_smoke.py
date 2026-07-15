#!/usr/bin/env python3
"""Parse and render the completed Mermaid diagram with a pinned Mermaid CLI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import ctypes
from pathlib import Path


MERMAID_CLI_VERSION = "11.12.0"
MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def find_browser() -> Path | None:
    candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    )
    configured = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if configured:
        candidates = (Path(configured), *candidates)
    return next((path for path in candidates if path.is_file()), None)


def windows_extended(path: Path) -> str:
    return "\\\\?\\" + str(path.absolute())


def exact_path_exists(path: Path) -> bool:
    """Check the exact root with Win32 APIs so long descendants cannot hide it."""
    if os.name != "nt":
        return os.path.lexists(path)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = int
    return get_attributes(windows_extended(path)) != -1


def remove_work_tree(path: Path, allowed_parent: Path) -> None:
    """Remove npm's long Windows cache paths and fail if the root can reappear."""
    if path.parent.resolve() != allowed_parent.resolve() or not path.name.startswith(".mermaid-smoke-"):
        raise RuntimeError(f"refusing unsafe temporary-directory cleanup: {path}")
    deadline = time.monotonic() + 20.0
    absent_since: float | None = None
    while time.monotonic() < deadline:
        if exact_path_exists(path):
            absent_since = None
            target: str | Path = windows_extended(path) if os.name == "nt" else path
            try:
                shutil.rmtree(target)
            except OSError:
                pass
        else:
            if absent_since is None:
                absent_since = time.monotonic()
            elif time.monotonic() - absent_since >= 2.0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"temporary render directory remains after cleanup: {path}")


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    document = Path(argv[1]) if len(argv) > 1 else root / "examples" / "completed-readonly-investigation-architecture.md"
    if len(argv) > 2:
        print("MERMAID RENDER FAILED\n- usage: render_mermaid_smoke.py [markdown-path]")
        return 1
    npx = shutil.which("npx")
    browser = find_browser()
    if npx is None or browser is None:
        print("MERMAID RENDER FAILED")
        print(f"- npx available: {str(npx is not None).lower()}")
        print(f"- Chrome or Edge available: {str(browser is not None).lower()}")
        return 1
    try:
        text = document.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"MERMAID RENDER FAILED\n- cannot read input: {exc}")
        return 1
    blocks = MERMAID_BLOCK.findall(text)
    if len(blocks) != 1:
        print(f"MERMAID RENDER FAILED\n- expected exactly one Mermaid block, found {len(blocks)}")
        return 1

    temp_parent = Path(tempfile.gettempdir()).resolve()
    work = Path(tempfile.mkdtemp(prefix=".mermaid-smoke-", dir=temp_parent))
    try:
        source = work / "diagram.mmd"
        output = work / "diagram.svg"
        config = work / "puppeteer-config.json"
        source.write_text(blocks[0].rstrip() + "\n", encoding="utf-8")
        config.write_text(json.dumps({"executablePath": str(browser)}), encoding="utf-8")
        env = os.environ.copy()
        env["npm_config_cache"] = str(work / "npm-cache")
        env["npm_config_audit"] = "false"
        env["npm_config_fund"] = "false"
        env["npm_config_update_notifier"] = "false"
        env["NO_UPDATE_NOTIFIER"] = "1"
        env["PUPPETEER_SKIP_DOWNLOAD"] = "true"
        command = [
            npx,
            "--yes",
            f"--package=@mermaid-js/mermaid-cli@{MERMAID_CLI_VERSION}",
            "mmdc",
            "--input",
            str(source),
            "--output",
            str(output),
            "--puppeteerConfigFile",
            str(config),
        ]
        completed = subprocess.run(command, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
        if completed.returncode != 0 or not output.is_file() or "<svg" not in output.read_text(encoding="utf-8"):
            print("MERMAID RENDER FAILED")
            if completed.stdout.strip():
                print(completed.stdout.strip())
            if completed.stderr.strip():
                print(completed.stderr.strip())
            return 1
        print("MERMAID RENDER VALID")
        print(f"architecture: {document.as_posix()}")
        print(f"renderer: @mermaid-js/mermaid-cli@{MERMAID_CLI_VERSION}")
        print(f"browser: {browser.name}")
        print("output: svg (temporary, removed after verification)")
        return 0
    finally:
        remove_work_tree(work, temp_parent)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
