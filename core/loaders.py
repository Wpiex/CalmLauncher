import json
import os

LOADERS = {"vanilla": "Vanilla", "fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge"}

def supported(loader):
    import minecraft_launcher_lib as mll
    return mll.mod_loader.get_mod_loader(loader).get_minecraft_versions(True)

def read_id(mc_dir):
    try:
        with open(os.path.join(mc_dir, "launch.json"), "r", encoding="utf-8") as f:
            return json.load(f)["id"]
    except Exception:
        return None

def write_id(mc_dir, version_id):
    with open(os.path.join(mc_dir, "launch.json"), "w", encoding="utf-8") as f:
        json.dump({"id": version_id}, f)

def install(loader, version, mc_dir, java, callback):
    import minecraft_launcher_lib as mll
    saved = read_id(mc_dir)
    saved_json = (
    os.path.join(mc_dir, "versions", saved, f"{saved}.json")
    if saved else ""
    ) 

    if saved and os.path.isfile(saved_json):
       return saved
    before = {v["id"] for v in mll.utils.get_installed_versions(mc_dir)}
    mll.mod_loader.get_mod_loader(loader).install(version, mc_dir, callback=callback, java=java)
    new = [v["id"] for v in mll.utils.get_installed_versions(mc_dir) if v["id"] not in before]
    if not new:
        raise RuntimeError("Loader installation failed")
    write_id(mc_dir, new[-1])
    return new[-1]
