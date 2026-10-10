import json
import os
import re
import shutil
from constants import INSTANCES

LOADER_IDS = ("fabric", "neoforge", "forge")
INSTALLING = set()

def instance_name(version, loader):
    return version if loader == "vanilla" else f"{version}-{loader}"

def instance_path(name):
    return os.path.join(INSTANCES, name)

def instance_dir(version, loader):
    path = instance_path(instance_name(version, loader))
    os.makedirs(path, exist_ok=True)
    return path

def meta_path(name):
    return os.path.join(instance_path(name), "instance.json")

def guess_meta(name):
    for loader in LOADER_IDS:
        suffix = "-" + loader
        if name.endswith(suffix):
            return {"version": name[:-len(suffix)], "loader": loader}
    return {"version": name, "loader": "vanilla"}

def read_meta(name):
    try:
        with open(meta_path(name), "r", encoding="utf-8") as file:
            metadata = json.load(file)
    except Exception:
        metadata = {}
    if "version" not in metadata or "loader" not in metadata:
        metadata.update(guess_meta(name))
    return metadata

def save_meta(name, metadata):
    with open(meta_path(name), "w", encoding="utf-8") as file:
        json.dump(metadata, file)

def safe_name(text):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text).strip(" .")

def new_name(version, loader, title):
    base = safe_name(title) if title else ""
    if not base:
        return instance_name(version, loader)
    name, index = base, 2
    while os.path.exists(instance_path(name)):
        name = f"{base} {index}"
        index += 1
    return name

def write_meta(name, version, loader, title=None):
    os.makedirs(instance_path(name), exist_ok=True)
    metadata = read_meta(name)
    metadata.update({"version": version, "loader": loader})
    if title:
        metadata["title"] = title
    save_meta(name, metadata)

def title(name):
    return read_meta(name).get("title") or name

def icon_path(name):
    path = os.path.join(instance_path(name), "icon.png")
    return path if os.path.isfile(path) else None

def is_installed(name):
    if name in INSTALLING:
        return True
    path = instance_path(name)
    return os.path.isfile(meta_path(name)) or os.path.isdir(os.path.join(path, "versions"))

def list_instances():
    try:
        names = [
            directory
            for directory in os.listdir(INSTANCES)
            if os.path.isdir(instance_path(directory)) and is_installed(directory)
        ]
    except OSError:
        return []
    return sorted(
        names,
        key=lambda name: [
            int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", name)
        ],
        reverse=True,
    )

def mods_dir(name):
    path = os.path.join(instance_path(name), "mods")
    os.makedirs(path, exist_ok=True)
    return path

def delete_instance(name):
    shutil.rmtree(instance_path(name))