import os
import re
import shutil
import subprocess
import sys

WINDOWS = sys.platform == "win32"
FLAGS = subprocess.CREATE_NO_WINDOW if WINDOWS else 0

def binary(home):
    names = ("javaw.exe", "java.exe") if WINDOWS else ("java",)
    for name in names:
        path = os.path.join(home, "bin", name)
        if os.path.isfile(path):
            return path
    return None

def normalize(path):
    path = os.path.normpath(path)
    if WINDOWS and os.path.basename(path).lower() == "java.exe":
        sibling = os.path.join(os.path.dirname(path), "javaw.exe")
        if os.path.isfile(sibling):
            return sibling
    return path

def major(path):
    probe = path
    if WINDOWS:
        sibling = os.path.join(os.path.dirname(path), "java.exe")
        if os.path.isfile(sibling):
            probe = sibling
    try:
        result = subprocess.run(
            [probe, "-version"], capture_output=True, text=True, timeout=10, creationflags=FLAGS
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "(\d+)(?:\.(\d+))?', result.stderr + result.stdout)
    if not match:
        return None
    first = int(match.group(1))
    return int(match.group(2) or 0) if first == 1 else first

def label(version, path):
    home = os.path.dirname(os.path.dirname(path))
    return f"Java {version} · {os.path.basename(home)}"

def describe(path):
    version = major(path)
    return None if version is None else label(version, path)

def walk(root, depth):
    if binary(root):
        yield root
        return
    if depth == 0:
        return
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return
    for name in names:
        child = os.path.join(root, name)
        if os.path.isdir(child):
            yield from walk(child, depth - 1)

def roots():
    result = []
    if WINDOWS:
        vendors = (
            "Java", "Eclipse Adoptium", "Microsoft", "Zulu", "BellSoft", "Amazon Corretto",
            "Semeru", "AdoptOpenJDK", "Eclipse Foundation", "Programs\\Eclipse Adoptium",
        )
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                result.extend((os.path.join(base, vendor), 1) for vendor in vendors)
        appdata = os.environ.get("APPDATA")
        if appdata:
            result.append((os.path.join(appdata, ".minecraft", "runtime"), 3))
    else:
        result.append(("/usr/lib/jvm", 1))
    return result

def find(extra=()):
    homes = []
    for root, depth in roots():
        homes.extend(walk(root, depth))
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        homes.append(java_home)
    found = shutil.which("java")
    if found and "javapath" not in found.lower():
        homes.append(os.path.dirname(os.path.dirname(os.path.realpath(found))))
    paths = [binary(home) for home in homes]
    paths.extend(normalize(path) for path in extra if path and os.path.isfile(path))
    seen = set()
    items = []
    for path in paths:
        if not path:
            continue
        path = os.path.normpath(path)
        key = os.path.normcase(os.path.realpath(path))
        if key in seen:
            continue
        seen.add(key)
        version = major(path)
        if version is not None:
            items.append((version, label(version, path), path))
    items.sort(key=lambda item: (-item[0], item[1]))
    return [(name, path) for _, name, path in items]
