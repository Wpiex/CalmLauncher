import json
import os
import requests

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "CalmLauncher/1.0"}
FOLDERS = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}
SORTS = {"Relevance": "relevance", "Downloads": "downloads", "Follows": "follows",
         "Newest": "newest", "Updated": "updated"}
PAGE = 20

def search(ptype, query, version, loader, sort, offset):
    facets = [[f"project_type:{ptype}"]]
    if version:
        facets.append([f"versions:{version}"])
    if ptype == "mod" and loader != "vanilla":
        facets.append([f"categories:{loader}"])
    r = requests.get(f"{API}/search", params={
        "query": query, "facets": json.dumps(facets), "index": sort,
        "limit": PAGE, "offset": offset}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    d = r.json()
    return d["hits"], d["total_hits"]

def pick_file(files):
    for f in files:
        if f.get("primary"):
            return f
    return files[0]

def fetch_bytes(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.content

def download(url, path):
    with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)

def install(project_id, ptype, version, loader, mc_dir, seen=None):
    seen = seen if seen is not None else set()
    if project_id in seen:
        return []
    seen.add(project_id)
    params = {"game_versions": json.dumps([version])}
    if ptype == "mod" and loader != "vanilla":
        params["loaders"] = json.dumps([loader])
    r = requests.get(f"{API}/project/{project_id}/version", params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    versions = r.json()
    if not versions:
        raise RuntimeError("No compatible file")
    v = next((x for x in versions if x["version_type"] == "release"), versions[0])
    f = pick_file(v["files"])
    folder = os.path.join(mc_dir, FOLDERS[ptype])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f["filename"])
    if not os.path.exists(path):
        download(f["url"], path)
    names = [f["filename"]]
    if ptype == "mod":
        for dep in v.get("dependencies", []):
            if dep.get("dependency_type") == "required" and dep.get("project_id"):
                try:
                    names += install(dep["project_id"], "mod", version, loader, mc_dir, seen)
                except Exception:
                    pass
    return names