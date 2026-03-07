"""OAuth authentication service for Google Sign-In."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BadRequestError
from app.core.security import create_access_token, create_refresh_token
from app.models.oauth import OAuthAccount, OAuthProvider
from app.models.user import User
from app.schemas.oauth import GoogleUserInfo, OAuthTokenResponse

logger = logging.getLogger(__name__)


class OAuthService:
    """Service for OAuth authentication flows."""

    def __init__(self, db: Session):
        self.db = db

    async def authenticate_with_google(
        self,
        code: str,
        redirect_uri: str,
    ) -> tuple[OAuthTokenResponse, str]:
        """
        Authenticate user with Google OAuth.
        
        Returns:
            Tuple of (OAuthTokenResponse, refresh_token)
            The refresh_token should be set as HTTP-only cookie.
        """
        # Exchange authorization code for tokens
        google_tokens = await self._exchange_google_code(code, redirect_uri)
        
        # Verify and decode ID token
        user_info = self._verify_google_id_token(google_tokens["id_token"])
        
        # Find or create user
        user, is_new = self._find_or_create_user(user_info)
        
        # Link or update OAuth account
        self._link_oauth_account(
            user=user,
            provider=OAuthProvider.GOOGLE,
            provider_user_id=user_info.google_id,
            provider_email=user_info.email,
            access_token=google_tokens.get("access_token"),
            refresh_token=google_tokens.get("refresh_token"),
            expires_in=google_tokens.get("expires_in"),
        )
        
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        
        # Generate JWT tokens
        access_token = create_access_token(user.id, user.username)
        refresh_token = create_refresh_token(user.id)
        
        response = OAuthTokenResponse(
            access_token=access_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            is_new_user=is_new,
            user_id=user.id,
            email=user.email,
        )
        
        return response, refresh_token

    async def _exchange_google_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for Google tokens."""
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise BadRequestError(
                message="Google OAuth is not configured",
                code="OAUTH_NOT_CONFIGURED",
            )
        
        token_url = "https://oauth2.googleapis.com/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Google token exchange failed: {response.text}")
                raise AuthenticationError(
                    message="Failed to authenticate with Google",
                    code="GOOGLE_AUTH_FAILED",
                )
            
            return response.json()

    def _verify_google_id_token(self, token: str) -> GoogleUserInfo:
        """Verify Google ID token and extract user info."""
        try:
            # Verify the token with clock skew tolerance (handles minor time differences)
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=10,  # Allow 10 seconds of clock skew
            )
            
            # Verify issuer
            if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
                raise AuthenticationError(
                    message="Invalid token issuer",
                    code="INVALID_TOKEN_ISSUER",
                )
            
            return GoogleUserInfo(
                google_id=idinfo["sub"],
                email=idinfo["email"],
                name=idinfo.get("name", idinfo["email"].split("@")[0]),
                picture=idinfo.get("picture"),
                email_verified=idinfo.get("email_verified", False),
            )
            
        except ValueError as e:
            logger.error(f"Google ID token verification failed: {e}")
            raise AuthenticationError(
                message="Invalid Google token",
                code="INVALID_GOOGLE_TOKEN",
            )

    def _find_or_create_user(self, user_info: GoogleUserInfo) -> tuple[User, bool]:
        """
        Find existing user by email or OAuth link, or create new user.
        
        Returns:
            Tuple of (User, is_new_user)
        """
        # First, check if user exists by OAuth link
        oauth_account = self.db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == OAuthProvider.GOOGLE,
                OAuthAccount.provider_user_id == user_info.google_id,
            )
        ).scalar_one_or_none()
        
        if oauth_account:
            return oauth_account.user, False
        
        # Check if user exists by email
        user = self.db.execute(
            select(User).where(User.email == user_info.email)
        ).scalar_one_or_none()
        
        if user:
            return user, False
        
        # Create new user
        # Generate unique username from email
        base_username = user_info.email.split("@")[0]
        username = self._generate_unique_username(base_username)
        
        user = User(
            name=user_info.name,
            username=username,
            email=user_info.email,
            password_hash=None,  # OAuth-only user, no password
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()  # Get the ID
        
        return user, True

    def _generate_unique_username(self, base: str) -> str:
        """Generate a unique username based on the base string."""
        username = base
        counter = 1
        
        while True:
            existing = self.db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            
            if not existing:
                return username
            
            username = f"{base}{counter}"
            counter += 1

    def _link_oauth_account(
        self,
        user: User,
        provider: OAuthProvider,
        provider_user_id: str,
        provider_email: str | None,
        access_token: str | None,
        refresh_token: str | None,
        expires_in: int | None,
    ) -> OAuthAccount:
        """Link or update OAuth account for user."""
        # Check if link already exists
        oauth_account = self.db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user.id,
                OAuthAccount.provider == provider,
            )
        ).scalar_one_or_none()
        
        token_expires_at = None
        if expires_in:
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        if oauth_account:
            # Update existing link
            oauth_account.provider_email = provider_email
            oauth_account.access_token = access_token
            oauth_account.refresh_token = refresh_token
            oauth_account.token_expires_at = token_expires_at
        else:
            # Create new link
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
            )
            self.db.add(oauth_account)
        
        self.db.flush()
        return oauth_account

    def get_linked_accounts(self, user_id: int) -> list[OAuthAccount]:
        """Get all OAuth accounts linked to a user."""
        return list(
            self.db.execute(
                select(OAuthAccount).where(OAuthAccount.user_id == user_id)
            ).scalars().all()
        )

    def unlink_account(self, user_id: int, provider: str) -> bool:
        """Unlink an OAuth account from user."""
        oauth_account = self.db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        ).scalar_one_or_none()
        
        if not oauth_account:
            return False
        
        # Check if user has password or other OAuth accounts
        user = self.db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user:
            return False
        
        other_accounts = self.db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider != provider,
            )
        ).scalars().all()
        
        # Prevent unlinking if it's the only auth method
        if not user.password_hash and len(list(other_accounts)) == 0:
            raise BadRequestError(
                message="Cannot unlink the only authentication method. Set a password first.",
                code="CANNOT_UNLINK_ONLY_AUTH",
            )
        
        self.db.delete(oauth_account)
        self.db.commit()
        return True
