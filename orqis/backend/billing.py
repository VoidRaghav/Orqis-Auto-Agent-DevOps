"""
Razorpay subscription billing.

Server-side only: creates plans/subscriptions and verifies payment signatures
with the secret key, which never leaves the backend. Uses httpx (already a
dependency) instead of the razorpay SDK to keep the dependency surface small.

Flow: create a plan for the requested price (reused across subscribers), create
a subscription against it, hand the subscription_id to the frontend checkout,
then verify the returned signature and record the subscription per workspace.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import config
from . import store
from .tenancy import tenant_prefix

_API = "https://api.razorpay.com/v1"
_TIMEOUT = 15.0


class BillingError(Exception):
    """A Razorpay call failed; carries an HTTP status for the endpoint to relay."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def configured() -> bool:
    return bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def _auth() -> tuple:
    return (config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)


# Immutable plan catalog. Prices are defined in USD (cents). The client can only
# choose a plan id and currency — never the amount — so the price can't be altered.
PLANS = {
    "pro": {"name": "Pro", "usd_cents": 1900},    # $19 / month
    "team": {"name": "Team", "usd_cents": 9900},  # $99 / month
}


def _amount_for(plan_id: str, currency: str) -> tuple:
    """(amount in smallest unit, currency) for a plan — enforced server-side."""
    plan = PLANS.get(plan_id)
    if plan is None:
        raise BillingError(400, f"unknown plan: {plan_id}")
    currency = (currency or "USD").upper()
    if currency == "USD":
        return plan["usd_cents"], "USD"
    if currency == "INR":
        # INR paise = usd_cents * rate (the /100 then *100 cancel). This always
        # charges the converted rupee amount, never the dollar number as rupees.
        return round(plan["usd_cents"] * config.USD_TO_INR), "INR"
    raise BillingError(400, f"unsupported currency: {currency}")


def _display(amount: int, currency: str) -> str:
    symbol = "$" if currency == "USD" else "₹"
    return f"{symbol}{amount / 100:.0f}"


def list_plans(currency: str = "USD") -> list:
    """Plan catalog with amounts in the requested currency, for the app to show."""
    out = []
    for pid, plan in PLANS.items():
        amount, cur = _amount_for(pid, currency)
        out.append({
            "id": pid,
            "name": plan["name"],
            "amount": amount,
            "currency": cur,
            "display": _display(amount, cur),
            "period": "monthly",
        })
    return out


def _raise_for(resp: httpx.Response, what: str) -> None:
    if resp.status_code == 401:
        raise BillingError(401, "Razorpay authentication failed - check the API keys")
    if resp.status_code >= 400:
        detail = resp.text[:200].replace("\n", " ")
        raise BillingError(502, f"Razorpay {what} failed: {detail}")


async def _plan_id_for(
    client: httpx.AsyncClient, amount: int, currency: str, period: str, interval: int
) -> str:
    """Reuse one plan per price so repeat subscribes don't spawn duplicate plans."""
    r = await store.get_redis()
    # Keyed by account so switching test -> live keys never reuses a foreign plan id.
    cache_key = f"orqis:razorpay:plan:{config.RAZORPAY_KEY_ID}:{currency}:{period}:{interval}:{amount}"
    cached = await r.get(cache_key)
    if cached:
        return cached
    resp = await client.post(
        f"{_API}/plans",
        auth=_auth(),
        json={
            "period": period,
            "interval": interval,
            "item": {
                "name": f"Orqis {amount / 100:.2f} {currency}/{period}",
                "amount": amount,
                "currency": currency,
            },
        },
    )
    _raise_for(resp, "plan creation")
    plan_id = resp.json()["id"]
    await r.set(cache_key, plan_id)  # plans are permanent - no TTL
    return plan_id


async def create_subscription(
    plan_id: str,
    currency: str = "USD",
    period: str = "monthly",
    interval: int = 1,
    total_count: int = 120,
) -> dict:
    if not configured():
        raise BillingError(503, "billing is not configured on this server")
    amount, cur = _amount_for(plan_id, currency)  # server-enforced price
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            plan_ref = await _plan_id_for(client, amount, cur, period, interval)
            resp = await client.post(
                f"{_API}/subscriptions",
                auth=_auth(),
                json={
                    "plan_id": plan_ref,
                    "total_count": total_count,
                    "quantity": 1,
                    "customer_notify": 1,
                    "notes": {"orqis_plan": plan_id},
                },
            )
    except httpx.HTTPError as e:
        raise BillingError(502, f"Razorpay unreachable: {e}") from e
    _raise_for(resp, "subscription creation")
    return {"subscription": resp.json(), "amount": amount, "currency": cur, "plan": plan_id}


def verify_signature(payment_id: str, subscription_id: str, signature: str) -> bool:
    """Subscription signature = HMAC_SHA256(payment_id + '|' + subscription_id)."""
    if not config.RAZORPAY_KEY_SECRET:
        return False
    expected = hmac.new(
        config.RAZORPAY_KEY_SECRET.encode(),
        f"{payment_id}|{subscription_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# --- Payment records (Postgres when configured; Redis fallback for local dev) ---

_PENDING_TTL = 3600  # redis fallback: window to match a payment to its plan


def _db_enabled() -> bool:
    return bool(config.DATABASE_URL)


async def ensure_schema() -> None:
    """Create the subscriptions table if a database is configured (idempotent)."""
    if not _db_enabled():
        return
    from . import db

    async with db.get_engine().begin() as conn:
        await conn.run_sync(db.SubscriptionRow.__table__.create, checkfirst=True)


def _record_from_row(row) -> dict:
    return {
        "subscription_id": row.razorpay_subscription_id,
        "payment_id": row.razorpay_payment_id,
        "plan": row.plan,
        "amount": row.amount,
        "currency": row.currency,
        "display": _display(row.amount, row.currency),
        "status": row.status,
        "github_login": row.github_login,
        "since": row.created_at.isoformat() if row.created_at else None,
    }


async def create_pending(
    tenant_id: str, subscription_id: str, plan: str, currency: str, github_id: Optional[int] = None
) -> dict:
    """Record the intended subscription with the SERVER price, before payment.
    verify() reads this back so the charged plan/amount can never be altered."""
    amount, cur = _amount_for(plan, currency)  # server-enforced
    if _db_enabled():
        import uuid

        from sqlalchemy import select

        from . import db

        async with db.session() as s:
            login = None
            if github_id is not None:
                u = (
                    await s.execute(select(db.User).where(db.User.github_id == github_id))
                ).scalar_one_or_none()
                login = u.github_login if u else None
            s.add(
                db.SubscriptionRow(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    razorpay_subscription_id=subscription_id,
                    plan=plan,
                    amount=amount,
                    currency=cur,
                    status="created",
                    github_id=github_id,
                    github_login=login,
                )
            )
    else:
        r = await store.get_redis()
        payload = {"tenant_id": tenant_id, "plan": plan, "amount": amount, "currency": cur}
        await r.set(
            f"orqis:razorpay:pending:{subscription_id}", json.dumps(payload), ex=_PENDING_TTL
        )
    return {"subscription_id": subscription_id, "plan": plan, "amount": amount, "currency": cur}


async def activate(tenant_id: str, subscription_id: str, payment_id: str) -> Optional[dict]:
    """Mark a verified payment active. Returns None if no matching pending record
    exists for this workspace (unknown/forged subscription)."""
    if _db_enabled():
        from sqlalchemy import select

        from . import db

        async with db.session() as s:
            row = (
                await s.execute(
                    select(db.SubscriptionRow).where(
                        db.SubscriptionRow.razorpay_subscription_id == subscription_id,
                        db.SubscriptionRow.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status = "active"
            row.razorpay_payment_id = payment_id
            await s.flush()
            return _record_from_row(row)
    r = await store.get_redis()
    raw = await r.get(f"orqis:razorpay:pending:{subscription_id}")
    if not raw:
        return None
    pend = json.loads(raw)
    if pend.get("tenant_id") != tenant_id:
        return None
    record = {
        "subscription_id": subscription_id,
        "payment_id": payment_id,
        "plan": pend["plan"],
        "amount": pend["amount"],
        "currency": pend["currency"],
        "display": _display(pend["amount"], pend["currency"]),
        "status": "active",
        "since": datetime.now(timezone.utc).isoformat(),
    }
    await r.set(f"{tenant_prefix()}subscription", json.dumps(record))
    await r.delete(f"orqis:razorpay:pending:{subscription_id}")
    return record


async def get_subscription(tenant_id: str) -> Optional[dict]:
    if _db_enabled():
        from sqlalchemy import select

        from . import db

        async with db.session() as s:
            row = (
                await s.execute(
                    select(db.SubscriptionRow)
                    .where(
                        db.SubscriptionRow.tenant_id == tenant_id,
                        db.SubscriptionRow.status == "active",
                    )
                    .order_by(db.SubscriptionRow.created_at.desc())
                )
            ).scalars().first()
            return _record_from_row(row) if row else None
    r = await store.get_redis()
    raw = await r.get(f"{tenant_prefix()}subscription")
    return json.loads(raw) if raw else None
