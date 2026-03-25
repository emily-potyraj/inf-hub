import os
from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-in-prod")
SESSION_COOKIE_NAME = "infhub_session"
SESSION_MAX_AGE = 8 * 60 * 60  # 8 hours

ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET", "")
ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID", "nvidia.onmicrosoft.com")
ENTRA_AUTHORIZE_URL = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/oauth2/v2.0/authorize"
ENTRA_TOKEN_URL = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/oauth2/v2.0/token"
ENTRA_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")


def _serializer():
    return URLSafeTimedSerializer(SESSION_SECRET)


def get_current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_auth(user=Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def create_session_cookie(response: Response, name: str, email: str):
    payload = {"name": name, "email": email}
    token = _serializer().dumps(payload)
    response.set_cookie(
        SESSION_COOKIE_NAME, token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
