import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse

from app.auth import (
    ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_AUTHORIZE_URL,
    ENTRA_TOKEN_URL, ENTRA_USERINFO_URL, REDIRECT_URI,
    create_session_cookie, clear_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login(request: Request):
    from urllib.parse import urlencode
    if not ENTRA_CLIENT_ID or not ENTRA_CLIENT_SECRET:
        return HTMLResponse(
            "<h2 style='font-family:sans-serif;padding:2rem'>Login not configured yet.<br>"
            "<small>Entra app registration pending — contact the team to set up "
            "<code>ENTRA_CLIENT_ID</code> and <code>ENTRA_CLIENT_SECRET</code>.</small></h2>",
            status_code=503,
        )
    params = {
        "client_id": ENTRA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email profile User.Read",
        "state": "infhub",
    }
    return RedirectResponse(f"{ENTRA_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
async def callback(request: Request, code: str, state: str = ""):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(ENTRA_TOKEN_URL, data={
            "client_id": ENTRA_CLIENT_ID,
            "client_secret": ENTRA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        })
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = await client.get(
            ENTRA_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = user_resp.json()

    name = user_data.get("displayName") or user_data.get("userPrincipalName", "Unknown")
    email = user_data.get("mail") or user_data.get("userPrincipalName", "")

    redirect = RedirectResponse(url="/", status_code=302)
    create_session_cookie(redirect, name, email)
    return redirect


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=302)
    clear_session_cookie(resp)
    return resp


@router.post("/dev-session")
def dev_session(payload: dict, response: Response):
    """Create a session cookie for testing. Only usable when SESSION_SECRET is the dev default."""
    import os
    if os.getenv("SESSION_SECRET", "dev-secret-change-in-prod") != "dev-secret-change-in-prod":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not available in production")
    create_session_cookie(response, payload.get("name", ""), payload.get("email", ""))
    return {"ok": True}
