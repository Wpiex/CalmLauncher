import time
import webbrowser

import requests


DEVICE_CODE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
)
TOKEN_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
)

XBOX_USER_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MINECRAFT_LOGIN_URL = (
    "https://api.minecraftservices.com/authentication/login_with_xbox"
)
MINECRAFT_PROFILE_URL = (
    "https://api.minecraftservices.com/minecraft/profile"
)


class OAuthError(Exception):
    pass


def _json_response(response):
    try:
        return response.json()
    except ValueError:
        return {"error_description": response.text}


def _check_response(response, label):
    data = _json_response(response)

    if not response.ok:
        details = (
            data.get("error_description")
            or data.get("Message")
            or data.get("message")
            or data.get("error")
            or response.text
        )
        raise OAuthError(f"{label}: {details}")

    return data


def microsoft_login(client_id, timeout=300, on_device_code=None):
    response = requests.post(
        DEVICE_CODE_URL,
        data={
            "client_id": client_id,
            "scope": "XboxLive.signin offline_access",
        },
        timeout=20,
    )
    device = _check_response(response, "Microsoft OAuth")

    device_code = device["device_code"]
    user_code = device["user_code"]
    verification_uri = device["verification_uri"]

    if on_device_code:
        on_device_code(verification_uri, user_code)

    webbrowser.open(verification_uri, new=2)

    interval = max(1, int(device.get("interval", 5)))
    deadline = time.monotonic() + min(
        timeout,
        int(device.get("expires_in", timeout)),
    )

    while time.monotonic() < deadline:
        time.sleep(interval)

        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            timeout=20,
        )

        token_data = _json_response(response)

        if response.ok:
            break

        error = token_data.get("error", "")

        if error == "authorization_pending":
            continue

        if error == "slow_down":
            interval += 5
            continue

        if error == "authorization_declined":
            raise OAuthError("Microsoft authorization was declined.")

        if error == "expired_token":
            raise OAuthError("Microsoft authorization code expired.")

        details = (
            token_data.get("error_description")
            or token_data.get("error")
            or response.text
        )
        raise OAuthError(f"Microsoft token: {details}")
    else:
        raise OAuthError("Microsoft authorization timed out.")

    microsoft_token = token_data["access_token"]

    response = requests.post(
        XBOX_USER_AUTH_URL,
        json={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": "d=" + microsoft_token,
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        },
        timeout=20,
    )
    xbox_data = _check_response(response, "Xbox Live")

    user_token = xbox_data["Token"]
    user_hash = xbox_data["DisplayClaims"]["xui"][0]["uhs"]

    response = requests.post(
        XSTS_URL,
        json={
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [user_token],
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT",
        },
        timeout=20,
    )
    xsts_data = _check_response(response, "Xbox XSTS")

    xsts_token = xsts_data["Token"]

    response = requests.post(
        MINECRAFT_LOGIN_URL,
        json={
            "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
        },
        timeout=20,
    )
    minecraft_data = _check_response(response, "Minecraft Services")

    minecraft_token = minecraft_data["access_token"]

    response = requests.get(
        MINECRAFT_PROFILE_URL,
        headers={
            "Authorization": f"Bearer {minecraft_token}"
        },
        timeout=20,
    )

    if response.status_code == 404:
        raise OAuthError(
            "No Minecraft Java profile was found on this Microsoft account."
        )

    profile = _check_response(response, "Minecraft profile")

    return {
        "name": profile["name"],
        "uuid": profile["id"],
        "token": minecraft_token,
        "type": "microsoft",
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": int(time.time())
        + int(minecraft_data.get("expires_in", 3600)),
    }
