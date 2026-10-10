from __future__ import annotations
import requests
from constants import ELY
from core.config import save_cfg

def _auth_base():
    base = str(ELY).rstrip("/")
    return base if base.endswith("/auth") else base + "/auth"

class AuthError(Exception):
    pass

class SessionExpired(Exception):
    pass

def _response_json(response):
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, requests.exceptions.JSONDecodeError):
        return {}

def _error_message(response, data, fallback):
    message = data.get("errorMessage") or data.get("message") or data.get("error")
    if message:
        return str(message)
    body = (getattr(response, "text", "") or "").strip()
    if body:
        return f"{fallback} (HTTP {response.status_code}): {body[:400]}"
    return f"{fallback} (HTTP {response.status_code})"

def login(cfg, username, password):
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        raise AuthError("Enter your Ely.by username and password.")

    client_token = cfg.get("client_token")
    if not client_token:
        raise AuthError(
            "The configuration has no client_token. Restart the launcher to recreate it."
        )

    try:
        response = requests.post(
            f"{_auth_base()}/authenticate",
            json={
                "username": username,
                "password": password,
                "clientToken": client_token,
                "requestUser": True,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise AuthError(
            f"Could not connect to Ely.by: {type(exc).__name__}: {exc}"
        ) from exc

    data = _response_json(response)
    if response.status_code != 200:
        raise AuthError(_error_message(response, data, "Ely.by login failed"))

    profile = data.get("selectedProfile")
    access_token = data.get("accessToken")
    if not isinstance(profile, dict) or not profile.get("id") or not profile.get("name"):
        raise AuthError(
            "Ely.by returned an incomplete profile. Check the server response and API address."
        )
    if not access_token:
        raise AuthError("Ely.by did not return an accessToken.")

    return {
        "name": str(profile["name"]),
        "uuid": str(profile["id"]),
        "token": str(access_token),
        "type": "ely",
    }

def ensure_session(cfg):
    account = cfg.get("account") or {}
    if str(account.get("type", "ely")).lower() != "ely":
        return

    access_token = account.get("token")
    client_token = cfg.get("client_token")
    if not access_token or not client_token:
        raise SessionExpired("The Ely.by session has no token. Please log in again.")

    try:
        validation = requests.post(
            f"{_auth_base()}/validate",
            json={"accessToken": access_token},
            timeout=15,
        )
        if validation.status_code == 200:
            return

        refresh = requests.post(
            f"{_auth_base()}/refresh",
            json={
                "accessToken": access_token,
                "clientToken": client_token,
                "requestUser": True,
            },
            timeout=20,
        )
    except requests.RequestException:
        return

    data = _response_json(refresh)
    if refresh.status_code != 200 or not data.get("accessToken"):
        raise SessionExpired(
            _error_message(refresh, data, "Ely.by session expired. Please log in again.")
        )

    account["token"] = str(data["accessToken"])
    profile = data.get("selectedProfile")
    if isinstance(profile, dict):
        if profile.get("name"):
            account["name"] = str(profile["name"])
        if profile.get("id"):
            account["uuid"] = str(profile["id"])
    cfg["account"] = account
    save_cfg(cfg)