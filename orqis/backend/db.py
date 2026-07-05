"""
Postgres layer — system of record for multi-tenancy.

Holds the durable account state that Redis (the fast, TTL'd live layer) must not
own: tenants, API keys, dashboard users, and per-tenant GitHub installations.
The engine is created lazily so the package imports cleanly with no DATABASE_URL
(single-tenant local dev); it is only required when MULTI_TENANT is on.
"""

import datetime as _dt
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .. import config

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def _async_url(url: str) -> str:
    """Normalize a Railway/Heroku-style URL to the asyncpg driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set — Postgres is unavailable")
        _engine = create_async_engine(
            _async_url(config.DATABASE_URL),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Async session scope — commits on success, rolls back on error."""
    async with get_sessionmaker()() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


async def init_models() -> None:
    """Create tables if they don't exist (dev convenience; prod uses Alembic)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- ORM models --------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class Tenant(Base):
    """A workspace. Every piece of ingested state is scoped to one tenant."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    github_account_login: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    installation: Mapped[Optional["GithubInstallation"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", uselist=False
    )


class ApiKey(Base):
    """A per-tenant SDK ingest key. Only the SHA-256 hash is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(20))  # e.g. "orqs_a1b2" for display
    name: Mapped[str] = mapped_column(String(120), default="default")
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


class User(Base):
    """A dashboard user, authenticated via GitHub OAuth, bound to one tenant."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    github_login: Mapped[str] = mapped_column(String(120))
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class GithubInstallation(Base):
    """A tenant's GitHub App installation — was the single global settings key."""

    __tablename__ = "github_installations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    account_login: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    repos: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    tenant: Mapped[Tenant] = relationship(back_populates="installation")
