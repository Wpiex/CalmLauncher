import os
import requests
from urllib.parse import urlparse

API = "https://api.curseforge.com/v1"
GAME_ID = 432
PAGE = 20
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "CalmLauncher/1.0",
}

CLASS_IDS = {
    "mod": 6,
    "resourcepack": 12,
    "shader": 6552,
}

LOADER_IDS = {
    "forge": 1,
    "fabric": 4,
    "quilt": 5,
    "neoforge": 6,
}

SORTS = {
    "Relevance": "relevancy",
    "Downloads": "downloads",
    "Popularity": "popularity",
    "Newest": "newest",
    "Updated": "updated",
}
SORT_FIELDS = {
    "popularity": 2,
    "updated": 3,
    "downloads": 6,
    "newest": 11,
    "relevancy": 13,
}
FOLDERS = {
    "mod": "mods",
    "resourcepack": "resourcepacks",
    "shader": "shaderpacks",
}


def _headers(api_key=None):
    key = (api_key or os.environ.get("CURSEFORGE_API_KEY", "")).strip()
    if not key:
        raise RuntimeError(
            "CurseForge requires an API key. Enter it in Content → Source → CurseForge."
        )
    return {**HEADERS, "x-api-key": key}


def _request_json(url, *, params=None, api_key=None, timeout=20):
    try:
        response = requests.get(
            url,
            params=params,
            headers=_headers(api_key),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"CurseForge connection failed: {exc}") from exc

    if response.status_code in (401, 403):
        raise RuntimeError(
            "CurseForge rejected the API key (401/403). Check the key and make sure "
            "your application is authorized to use the CurseForge API."
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"CurseForge API error: HTTP {response.status_code}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("CurseForge returned an invalid response.") from exc


def search(ptype, query, version, loader, sort, offset, api_key=None):
    if ptype not in CLASS_IDS:
        raise ValueError(f"Unsupported CurseForge content type: {ptype}")

    params = {
        "gameId": GAME_ID,
        "classId": CLASS_IDS[ptype],
        "index": max(0, int(offset)),
        "pageSize": PAGE,
        "sortField": SORT_FIELDS.get(sort, SORT_FIELDS["relevancy"]),
        "sortOrder": "desc",
    }
    if query:
        params["searchFilter"] = query
    if version:
        params["gameVersion"] = version

    if ptype == "mod" and loader and loader != "vanilla":
        loader_id = LOADER_IDS.get(str(loader).lower())
        if loader_id is not None:
            params["modLoaderType"] = loader_id

    data = _request_json(f"{API}/mods/search", params=params, api_key=api_key)
    hits = []
    for mod in data.get("data", []):
        authors = mod.get("authors") or []
        author = ", ".join(
            str(item.get("name", "")).strip()
            for item in authors
            if isinstance(item, dict) and item.get("name")
        ) or "Unknown author"
        logo = mod.get("logo") or {}
        hits.append({
            "project_id": str(mod.get("id", "")),
            "title": mod.get("name") or "Untitled project",
            "author": author,
            "downloads": int(mod.get("downloadCount") or 0),
            "icon_url": logo.get("url") if isinstance(logo, dict) else None,
        })

    pagination = data.get("pagination") or {}
    total = int(pagination.get("totalCount", len(hits)))
    return hits, total


def fetch_bytes(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.content
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not download image: {exc}") from exc


def download(url, path, api_key=None):
    host = (urlparse(url).hostname or "").lower()
    headers = _headers(api_key) if (host == "forgecdn.net" or host.endswith(".forgecdn.net")) else HEADERS
    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(path, "wb") as file:
                for chunk in response.iter_content(65536):
                    if chunk:
                        file.write(chunk)
    except requests.RequestException as exc:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        raise RuntimeError(f"CurseForge download failed: {exc}") from exc


def _compatible_files(project_id, ptype, version, loader, api_key):
    params = {"index": 0, "pageSize": 50}
    if version:
        params["gameVersion"] = version
    if ptype == "mod" and loader and loader != "vanilla":
        loader_id = LOADER_IDS.get(str(loader).lower())
        if loader_id is not None:
            params["modLoaderType"] = loader_id

    data = _request_json(
        f"{API}/mods/{int(project_id)}/files",
        params=params,
        api_key=api_key,
    )
    files = [item for item in data.get("data", []) if item.get("isAvailable", True)]
    if not files:
        raise RuntimeError("No compatible CurseForge file was found for this Minecraft version/loader.")

    files.sort(
        key=lambda item: (
            item.get("releaseType") == 1,
            item.get("fileDate") or "",
        ),
        reverse=True,
    )
    return files


def _download_url(project_id, file_info, api_key):
    url = file_info.get("downloadUrl")
    if url:
        return url

    file_id = file_info.get("id")
    if not file_id:
        raise RuntimeError("CurseForge did not provide a file ID for downloading.")
    data = _request_json(
        f"{API}/mods/{int(project_id)}/files/{int(file_id)}/download-url",
        api_key=api_key,
    )
    url = data.get("data")
    if not url:
        raise RuntimeError(
            "CurseForge does not provide a direct download for this file. "
            "Try another project or file."
        )
    return url


def install(project_id, ptype, version, loader, mc_dir, api_key=None, seen=None):
    if ptype not in FOLDERS:
        raise ValueError(f"Unsupported CurseForge content type: {ptype}")

    key = (api_key or os.environ.get("CURSEFORGE_API_KEY", "")).strip()
    _headers(key)
    seen = seen if seen is not None else set()
    project_id = int(project_id)
    if project_id in seen:
        return []
    seen.add(project_id)

    files = _compatible_files(project_id, ptype, version, loader, key)
    file_info = files[0]
    filename = os.path.basename(file_info.get("fileName") or "")
    if not filename:
        raise RuntimeError("CurseForge returned a file without a filename.")

    folder = os.path.join(mc_dir, FOLDERS[ptype])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        url = _download_url(project_id, file_info, key)
        download(url, path, api_key=key)

    installed = [filename]
    if ptype == "mod":
        for dependency in file_info.get("dependencies", []):
            if dependency.get("relationType") != 3 or not dependency.get("modId"):
                continue
            try:
                installed.extend(
                    install(
                        dependency["modId"],
                        "mod",
                        version,
                        loader,
                        mc_dir,
                        api_key=key,
                        seen=seen,
                    )
                )
            except Exception:
                continue
    return installed
