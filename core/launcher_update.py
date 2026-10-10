from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

OWNER = "Wpiex"
REPOSITORY = "CalmLauncher"
LATEST_RELEASE_API = f"https://api.github.com/repos/{OWNER}/{REPOSITORY}/releases/latest"
USER_AGENT = "CalmLauncher-Updater/1.0"
CURRENT_VERSION = "1.0p2"
EXE_NAME = "Calm Launcher.exe"
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_UNPACKED_BYTES = 1_500 * 1024 * 1024

SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", ".idea",
    "build", "dist", "Instances", "instances", "logs", "crash-reports",
    "TempAudios", "SavedAudios",
}
SKIP_FILES = {".env", ".ds_store", "settings.txt"}

class NoReleases(RuntimeError):
    pass

def _version_key(value: str) -> tuple[int, ...]:
    digits = re.findall(r"\d+", str(value or ""))
    return tuple(int(part) for part in digits) if digits else (0,)


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            import json
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NoReleases(
                "No GitHub releases have been published yet. Create a release and upload a ZIP file as a release asset."
            ) from exc
        if exc.code in (403, 429):
            raise RuntimeError("GitHub API rate limit reached. Try again later.") from exc
        raise RuntimeError(f"GitHub update check failed (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Check your Internet connection.") from exc


def check_latest_release(current_version: str = CURRENT_VERSION):
    current_version = max(str(current_version or ''), CURRENT_VERSION, key=_version_key)
    try:
        release = _request_json(LATEST_RELEASE_API)
    except NoReleases:
        return None
    tag = str(release.get("tag_name") or release.get("name") or "").strip()
    if not tag:
        raise RuntimeError("The latest GitHub release does not have a version tag.")

    assets = [
        asset for asset in (release.get("assets") or [])
        if str(asset.get("name") or "").lower().endswith(".zip")
        and str(asset.get("browser_download_url") or "").startswith("https://")
    ]
    if not assets:
        raise RuntimeError(
            "The latest GitHub release has no ZIP asset. Upload the launcher package ZIP in the release Assets section."
        )
    assets.sort(key=lambda item: ("calmlauncher" not in str(item.get("name", "")).lower(),
                                  str(item.get("name", "")).lower()))
    asset = assets[0]

    if _version_key(tag) <= _version_key(current_version):
        return None

    return {
        "tag_name": tag,
        "name": str(release.get("name") or tag),
        "body": str(release.get("body") or "").strip(),
        "html_url": str(release.get("html_url") or f"https://github.com/{OWNER}/{REPOSITORY}/releases"),
        "asset_name": str(asset.get("name") or "CalmLauncher.zip"),
        "asset_url": str(asset.get("browser_download_url") or ""),
        "published_at": str(release.get("published_at") or ""),
    }


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    total_size = 0
    with zipfile.ZipFile(archive_path, "r") as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            relative = PurePosixPath(name)
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise RuntimeError("The update ZIP contains an unsafe file path.")
            if ":" in relative.parts[0]:
                raise RuntimeError("The update ZIP contains an unsafe file path.")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError("The update ZIP contains a symbolic link; installation was cancelled.")
            total_size += int(info.file_size or 0)
            if total_size > MAX_UNPACKED_BYTES:
                raise RuntimeError("The update ZIP is too large to unpack safely.")

            output = destination.joinpath(*relative.parts)
            try:
                output.resolve().relative_to(destination_resolved)
            except ValueError as exc:
                raise RuntimeError("The update ZIP contains an unsafe file path.") from exc
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, output.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)


def _find_project_root(extracted: Path) -> Path:
    if is_frozen():
        for current, _, files in os.walk(extracted):
            if EXE_NAME in files:
                return Path(current)
        raise RuntimeError("The release ZIP does not contain Calm Launcher.exe.")
    for current, directories, files in os.walk(extracted):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        current_path = Path(current)
        if "main.py" in files and "constants.py" in files:
            if (current_path / "core").is_dir() and (current_path / "ui").is_dir():
                return current_path
    raise RuntimeError(
        "The release ZIP does not contain the Calm Launcher source layout (main.py, constants.py, core/, ui/)."
    )


def _iter_release_files(source_root: Path):
    for current, directories, files in os.walk(source_root):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        base = Path(current)
        for filename in files:
            lower = filename.lower()
            if lower in SKIP_FILES or lower.startswith(".env.") or lower.endswith((".pyc", ".log")):
                continue
            path = base / filename
            if path.is_symlink() or not path.is_file():
                continue
            yield path


def _stage_frozen_update(source_root: Path, app_root: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix="calmlauncher-staged-"))
    shutil.copytree(source_root, staging, dirs_exist_ok=True)
    script = staging.parent / f"{staging.name}.bat"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f"set PID={os.getpid()}",
        ":wait",
        'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul',
        "if not errorlevel 1 (",
        "    ping 127.0.0.1 -n 2 >nul",
        "    goto wait",
        ")",
        f'xcopy "{staging}\\*" "{app_root}" /E /Y /I /Q >nul',
        f'if exist "{app_root}\\_internal" rmdir /S /Q "{app_root}\\_internal"',
        f'rmdir /S /Q "{staging}"',
        f'start "" "{app_root / EXE_NAME}"',
        '(goto) 2>nul & del "%~f0"',
    ]
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd.exe", "/c", str(script)], creationflags=flags, close_fds=True)


def install_release_zip(asset_url: str, release_version: str = "") -> str:
    if not str(asset_url).startswith("https://"):
        raise RuntimeError("The release download URL is invalid.")

    app_root = _app_root().resolve()
    with tempfile.TemporaryDirectory(prefix="calmlauncher-update-") as temp_name:
        temp = Path(temp_name)
        archive_path = temp / "release.zip"
        request = urllib.request.Request(asset_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response, archive_path.open("wb") as output:
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("The update ZIP is too large to download safely.")
                total = 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_ARCHIVE_BYTES:
                        raise RuntimeError("The update ZIP is too large to download safely.")
                    output.write(block)
        except RuntimeError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("Could not download the update. Check your Internet connection.") from exc

        extracted = temp / "extracted"
        extracted.mkdir()
        _safe_extract(archive_path, extracted)
        source_root = _find_project_root(extracted)
        if is_frozen():
            _stage_frozen_update(source_root, app_root)
            return str(release_version or "installed")
        files = list(_iter_release_files(source_root))
        if not files:
            raise RuntimeError("The update ZIP contains no installable files.")

        backup_root = temp / "backup"
        changed = []
        try:
            for source in files:
                relative = source.relative_to(source_root)
                target = (app_root / relative).resolve()
                try:
                    target.relative_to(app_root)
                except ValueError as exc:
                    raise RuntimeError("The update contains a file outside the launcher directory.") from exc

                target.parent.mkdir(parents=True, exist_ok=True)
                existed = target.exists()
                backup = backup_root / relative
                if existed:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                changed.append((target, backup, existed))
                shutil.copy2(source, target)
        except Exception as exc:
            rollback_errors = []
            for target, backup, existed in reversed(changed):
                try:
                    if existed and backup.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup, target)
                    elif not existed and target.exists():
                        target.unlink()
                except OSError as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if rollback_errors:
                raise RuntimeError(
                    f"Update failed and rollback was incomplete: {exc}; {'; '.join(rollback_errors[:3])}"
                ) from exc
            raise RuntimeError(f"Could not install the update: {exc}") from exc

    return str(release_version or "installed")
