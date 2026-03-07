"""OAuth authentication schemas."""

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class GoogleAuthRequest(BaseSchema):
    """Request schema for Google OAuth authentication."""

    code: str = Field(..., description="Authorization code from Google")
    redirect_uri: str = Field(..., description="Redirect URI used in the OAuth flow")


class GoogleUserInfo(BaseSchema):
    """Google user info extracted from ID token."""

    google_id: str
    email: EmailStr
    name: str
    picture: str | None = None
    email_verified: bool = False


class OAuthAccountResponse(BaseSchema):
    """OAuth account response schema."""

    id: int
    provider: str
    provider_email: str | None
    created_at: datetime


class OAuthTokenResponse(BaseSchema):
    """OAuth authentication response with tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool = False
    user_id: int
    email: str | None = None


class LinkGoogleRequest(BaseSchema):
    """Request to link Google account to existing user."""

    code: str = Field(..., description="Authorization code from Google")
    redirect_uri: str = Field(..., description="Redirect URI used in the OAuth flow")


class SessionRestoreResponse(BaseSchema):
    """Response for session restoration from refresh token cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
