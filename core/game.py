import os
import shutil
import subprocess
import requests
from constants import AGENT, ELY_AGENT
from core.auth import ensure_session
from core.instances import instance_path, new_name, is_installed, write_meta, read_meta, INSTALLING
from core import loaders, modrinth, optimize

class Cancelled(Exception):
    pass

def check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled("Cancelled")

def ensure_agent(progress):
    if os.path.exists(AGENT):
        return
    progress("Downloading authlib-injector", 0)
    url = requests.get("https://authlib-injector.yushi.moe/artifact/latest.json",
                       timeout=15).json()["download_url"]
    with open(AGENT, "wb") as f:
        f.write(requests.get(url, timeout=60).content)

def callbacks(progress, cancel=None):
    state = {"max": 1}

    def status(t):
        check(cancel)
        progress(t, -1)

    def set_max(v):
        check(cancel)
        state["max"] = v or 1

    def set_progress(v):
        check(cancel)
        progress("", int(v * 100 / state["max"]))

    return {"setStatus": status, "setMax": set_max, "setProgress": set_progress}

def runtime(mll, version, mc_dir, cb=None):
    info = mll.runtime.get_version_runtime_information(version, mc_dir)
    if not info:
        return None
    if cb:
        mll.runtime.install_jvm_runtime(info["name"], mc_dir, callback=cb)
    return mll.runtime.get_executable_path(info["name"], mc_dir)

def install(version, loader, progress, title=None, cancel=None, extra=None):
    import minecraft_launcher_lib as mll

    name = new_name(version, loader, title)
    fresh = not is_installed(name)
    INSTALLING.add(name)
    mc_dir = instance_path(name)
    os.makedirs(mc_dir, exist_ok=True)
    cb = callbacks(progress, cancel)
    warn = None
    try:
        progress("Installing Minecraft", 0)
        mll.install.install_minecraft_version(version, mc_dir, callback=cb)
        check(cancel)
        exe = runtime(mll, version, mc_dir, cb)
        check(cancel)
        if loader != "vanilla":
            progress(f"Installing {loader}", 0)
            loaders.install(loader, version, mc_dir, exe, cb)
            check(cancel)
        write_meta(name, version, loader, title)
        if extra and loader != "vanilla":
            progress(f"Installing {extra}", 0)
            try:
                modrinth.install(optimize.SLUGS[extra], "mod", version, loader, mc_dir)
            except Exception as e:
                warn = f"{extra}: {e}"
    except Exception:
        if fresh:
            shutil.rmtree(mc_dir, ignore_errors=True)
        raise
    finally:
        INSTALLING.discard(name)
    return warn

def run(cfg, name, progress):
    import minecraft_launcher_lib as mll

    meta = read_meta(name)
    version = meta.get("version")
    loader = meta.get("loader", "vanilla")

    if not version:
        raise RuntimeError("Instance has no Minecraft version")

    mc_dir = instance_path(name)

    if not os.path.isdir(mc_dir):
        raise RuntimeError("Instance folder does not exist")

    acc = cfg.get("account")
    if not isinstance(acc, dict) or not acc:
        raise RuntimeError("Please log in first")

    ely = acc.get("type", "ely") == "ely"

    progress("Checking session", 0)
    ensure_session(cfg)

    if ely:
        ensure_agent(progress)

    cb = callbacks(progress)
    target = version

    if loader != "vanilla":
        target = loaders.read_id(mc_dir)

        target_json = (
            os.path.join(mc_dir, "versions", target, f"{target}.json")
            if target else ""
        )

        if not target or not os.path.isfile(target_json):
            progress(f"Repairing {loader} installation", 0)

            java = runtime(mll, version, mc_dir, cb)
            target = loaders.install(
                loader, version, mc_dir, java, cb
            )

            target_json = os.path.join(
                mc_dir, "versions", target, f"{target}.json"
            )

            if not os.path.isfile(target_json):
                raise RuntimeError(
                    f"{loader} installation is incomplete"
                )

    progress("Checking Minecraft files and libraries", 0)
    mll.install.install_minecraft_version(
        version, mc_dir, callback=cb
    )

    if target != version:
        progress("Checking loader libraries", 0)
        mll.install.install_minecraft_version(
            target, mc_dir, callback=cb
        )

    custom = str(cfg.get("java_path") or "")
    if custom and os.path.isfile(custom):
        exe = custom
    else:
        exe = runtime(mll, version, mc_dir, cb)

    mem = cfg["memory"]
    extra_args = str(cfg.get("java_args") or "").split()
    jvm = [f"-Xmx{mem}M", f"-Xms{min(mem, 1024)}M", *extra_args]

    if ely:
        jvm.insert(0, f"-javaagent:{AGENT}={ELY_AGENT}")

    opts = {
        "username": acc["name"],
        "uuid": acc["uuid"],
        "token": acc["token"],
        "jvmArguments": jvm,
    }

    if exe:
        opts["executablePath"] = exe

    apply_language(mc_dir, cfg.get("lang", "en"))

    progress("Launching", 100)

    cmd = mll.command.get_minecraft_command(
        target, mc_dir, opts
    )
    creation_flags = 0
    if os.name == "nt":
     creation_flags = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(
    cmd,
    cwd=mc_dir,
    creationflags=creation_flags,
    )   

LANGS = {"en": "en_us", "ru": "ru_ru"}

def apply_language(mc_dir, lang):
    code = LANGS.get(lang, "en_us")
    path = os.path.join(mc_dir, "options.txt")
    lines = []
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        for index, line in enumerate(lines):
            if line.startswith("lang:"):
                lines[index] = f"lang:{code}"
                break
        else:
            lines.append(f"lang:{code}")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass

def crash_file(name, since):
    base = instance_path(name)
    folder = os.path.join(base, "crash-reports")
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".txt")]
    except OSError:
        files = []
    files = [f for f in files if os.path.getmtime(f) >= since]
    if files:
        return max(files, key=os.path.getmtime)
    log = os.path.join(base, "logs", "latest.log")
    return log if os.path.isfile(log) else None