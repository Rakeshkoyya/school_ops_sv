"""OAuth authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.core.security import set_refresh_cookie, clear_auth_cookies, verify_refresh_token, create_access_token
from app.models.audit import AuditAction
from app.schemas.oauth import (
    GoogleAuthRequest,
    LinkGoogleRequest,
    OAuthAccountResponse,
    OAuthTokenResponse,
    SessionRestoreResponse,
)
from app.schemas.common import MessageResponse
from app.services.audit import AuditService
from app.services.oauth import OAuthService

router = APIRouter()


@router.post("/google", response_model=OAuthTokenResponse)
async def google_auth(
    request: GoogleAuthRequest,
    response: Response,
    http_request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Authenticate with Google OAuth.
    
    Exchange Google authorization code for JWT tokens.
    The refresh token is set as an HTTP-only cookie for session persistence.
    """
    service = OAuthService(db)
    token_response, refresh_token = await service.authenticate_with_google(
        code=request.code,
        redirect_uri=request.redirect_uri,
    )
    
    # Set refresh token as HTTP-only cookie
    set_refresh_cookie(response, refresh_token)
    
    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.USER_LOGIN,
        resource_type="user",
        resource_id=str(token_response.user_id),
        user_id=token_response.user_id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
        metadata={"method": "google_oauth", "is_new_user": token_response.is_new_user},
    )
    
    return token_response


@router.get("/session", response_model=SessionRestoreResponse)
async def restore_session(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: str | None = Cookie(None, alias="refresh_token"),
):
    """
    Restore session from HTTP-only refresh token cookie.
    
    This endpoint is called on page load to restore the user's session
    without requiring them to log in again.
    
    Returns a new access token if the refresh token is valid.
    """
    from app.core.exceptions import AuthenticationError
    from app.models.user import User
    from sqlalchemy import select
    
    if not refresh_token:
        raise AuthenticationError(
            message="No refresh token found",
            code="NO_REFRESH_TOKEN",
        )
    
    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    if not payload:
        # Clear invalid cookie
        clear_auth_cookies(response)
        raise AuthenticationError(
            message="Invalid or expired session",
            code="INVALID_SESSION",
        )
    
    # Get user
    user_id = int(payload.get("sub", 0))
    user = db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    ).scalar_one_or_none()
    
    if not user:
        clear_auth_cookies(response)
        raise AuthenticationError(
            message="User not found or inactive",
            code="USER_NOT_FOUND",
        )
    
    # Generate new access token
    access_token = create_access_token(user.id, user.username)
    
    return SessionRestoreResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    response: Response,
    http_request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Logout user by clearing auth cookies.
    """
    clear_auth_cookies(response)
    
    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.USER_LOGOUT,
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
    )
    
    return MessageResponse(message="Successfully logged out")


@router.get("/linked-accounts", response_model=list[OAuthAccountResponse])
def get_linked_accounts(
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Get all OAuth accounts linked to the current user.
    """
    service = OAuthService(db)
    accounts = service.get_linked_accounts(current_user.id)
    return accounts


@router.post("/link/google", response_model=OAuthAccountResponse)
async def link_google_account(
    request: LinkGoogleRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Link Google account to the current user.
    """
    from app.core.exceptions import ConflictError
    from app.models.oauth import OAuthAccount, OAuthProvider
    from sqlalchemy import select
    
    service = OAuthService(db)
    
    # Exchange code and get user info
    google_tokens = await service._exchange_google_code(request.code, request.redirect_uri)
    user_info = service._verify_google_id_token(google_tokens["id_token"])
    
    # Check if this Google account is already linked to another user
    existing = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == OAuthProvider.GOOGLE,
            OAuthAccount.provider_user_id == user_info.google_id,
        )
    ).scalar_one_or_none()
    
    if existing and existing.user_id != current_user.id:
        raise ConflictError(
            message="This Google account is already linked to another user",
            code="GOOGLE_ACCOUNT_LINKED",
        )
    
    # Link the account
    oauth_account = service._link_oauth_account(
        user=current_user,
        provider=OAuthProvider.GOOGLE,
        provider_user_id=user_info.google_id,
        provider_email=user_info.email,
        access_token=google_tokens.get("access_token"),
        refresh_token=google_tokens.get("refresh_token"),
        expires_in=google_tokens.get("expires_in"),
    )
    
    # Update user email if not set
    if not current_user.email:
        current_user.email = user_info.email
    
    db.commit()
    
    return oauth_account


@router.delete("/linked-accounts/{provider}", response_model=MessageResponse)
def unlink_account(
    provider: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Unlink an OAuth account from the current user.
    """
    from app.core.exceptions import NotFoundError
    
    service = OAuthService(db)
    success = service.unlink_account(current_user.id, provider)
    
    if not success:
        raise NotFoundError(
            resource=f"{provider.title()} account",
            identifier=provider,
        )
    
    return MessageResponse(message=f"{provider.title()} account unlinked successfully")
