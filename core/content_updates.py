import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.modrinth.com/v2"
HEADERS = {
    "User-Agent": "CalmLauncher/1.0",
    "Accept": "application/json",
}

FOLDERS = {
    "mod": ("mods", (".jar",)),
    "resourcepack": ("resourcepacks", (".zip",)),
    "shader": ("shaderpacks", (".zip",)),
}

def sha1_file(path):
    digest = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _request_json(url, data=None, timeout=25):
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def _loader_filter(ptype, loader):
    if ptype == "resourcepack":
        return ["minecraft"]
    if ptype == "shader":
        return ["iris", "optifine"]
    if loader and loader != "vanilla":
        return [str(loader).lower()]
    return ["fabric", "forge", "neoforge", "quilt"]

def latest_update_for_file(path, game_version, loader, ptype):
    if ptype not in FOLDERS or not os.path.isfile(path):
        return None
    current_hash = sha1_file(path)
    query = urllib.parse.urlencode({"algorithm": "sha1"})
    url = f"{API}/version_file/{current_hash}/update?{query}"
    body = {
        "loaders": _loader_filter(ptype, loader),
        "game_versions": [str(game_version)],
        "version_types": ["release", "beta", "alpha"],
    }
    try:
        update = _request_json(url, body)
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return None
        raise

    if not isinstance(update, dict):
        return None
    files = update.get("files") or []
    if not files:
        return None

    latest_file = next((item for item in files if item.get("primary")), files[0])
    latest_hashes = {
        str(item.get("hashes", {}).get("sha1", "")).lower()
        for item in files
        if item.get("hashes", {}).get("sha1")
    }
    if current_hash.lower() in latest_hashes:
        return None

    if not latest_file.get("url") or not latest_file.get("filename"):
        return None
    return {
        "project_id": update.get("project_id"),
        "version_id": update.get("id"),
        "version_number": str(update.get("version_number") or update.get("name") or "latest"),
        "name": str(update.get("name") or update.get("version_number") or "Modrinth content"),
        "file": latest_file,
    }

def instance_content_files(instance_root):
    found = []
    seen = set()
    for ptype, (folder, extensions) in FOLDERS.items():
        for base in (instance_root, os.path.join(instance_root, "minecraft")):
            directory = os.path.join(base, folder)
            if not os.path.isdir(directory):
                continue
            try:
                names = os.listdir(directory)
            except OSError:
                continue
            for name in names:
                path = os.path.abspath(os.path.join(directory, name))
                if path in seen or not os.path.isfile(path):
                    continue
                if not name.lower().endswith(extensions):
                    continue
                seen.add(path)
                found.append({"path": path, "ptype": ptype})
    return found

def check_instance(instance_root, game_version, loader):
    updates = []
    for item in instance_content_files(instance_root):
        info = latest_update_for_file(
            item["path"], game_version, loader, item["ptype"]
        )
        if info:
            updates.append({
                "path": item["path"],
                "ptype": item["ptype"],
                "update": info,
            })
    return updates

def apply_update(path, update_info):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    file_info = update_info.get("file") or {}
    url = str(file_info.get("url") or "")
    filename = str(file_info.get("filename") or "")
    if not url.startswith("https://cdn.modrinth.com/") or not filename:
        raise ValueError("Invalid Modrinth update file")

    folder = os.path.dirname(os.path.abspath(path))
    safe_filename = os.path.basename(filename.replace("\\", "/"))
    target = os.path.join(folder, safe_filename)
    fd, temporary = tempfile.mkstemp(prefix=".calm-update-", suffix=".tmp", dir=folder)
    os.close(fd)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(request, timeout=90) as response, open(temporary, "wb") as output:
            shutil.copyfileobj(response, output)

        expected_sha1 = str(file_info.get("hashes", {}).get("sha1", "")).lower()
        if expected_sha1 and sha1_file(temporary).lower() != expected_sha1:
            raise ValueError("Downloaded file hash does not match Modrinth")

        if os.path.normcase(target) != os.path.normcase(os.path.abspath(path)):
            if os.path.exists(target):
                if expected_sha1 and sha1_file(target).lower() == expected_sha1:
                    os.remove(path)
                    return target
                raise FileExistsError(f"Another file already exists: {safe_filename}")
            os.replace(temporary, target)
            os.remove(path)
            return target

        os.replace(temporary, path)
        return path
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass