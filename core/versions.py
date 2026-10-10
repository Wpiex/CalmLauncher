import re
import minecraft_launcher_lib

def version_key(version):
    return tuple(int(part) for part in re.findall(r"\d+", version))

def get_versions():
    available = minecraft_launcher_lib.utils.get_version_list()
    versions = [
        item["id"]
        for item in available
        if item.get("type") == "release"
    ]
    minimum = version_key("1.12.2")
    versions = [version for version in versions if version_key(version) >= minimum]
    return sorted(versions, key=version_key)