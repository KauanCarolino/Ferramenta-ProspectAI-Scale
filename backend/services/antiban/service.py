"""Anti-ban — rate limit, warm-up, round-robin, proxies, circuit breaker.

Warm-up (`Account.warmup_day`)
------------------------------
Cap diário por conta (quando ``antiban_warmup_enabled``):

- Dia efetivo 1 → 20 DMs
- Dia 2 → 40
- Dia 3 → 60
- Dia 4+ → ``antiban_max_dm_per_account_per_day``

``warmup_day == 0`` + status ``warming`` → trata como dia 1.
``warmup_day == 0`` + status ``active`` → trata como dia 4+ (cota cheia; contas
já maduras sem rampa explícita).

Incremento: ``maybe_advance_warmup`` só sobe ``warmup_day`` no **rollover**
UTC (quando ``messages_today == 0`` e o dia civil anterior atingiu o cap).
Assim o Dia 1 continua limitado a 20 DMs no mesmo dia — a cota 40 só vale
no dia seguinte. Quando ``warmup_day`` chega a 4 e o status era ``warming``,
promove para ``active``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.message import Message

logger = logging.getLogger(__name__)

ELIGIBLE_ACCOUNT_STATUSES = frozenset({"active", "warming"})
WARMUP_CAPS: dict[int, int] = {1: 20, 2: 40, 3: 60}
FAILURE_RESULTS = frozenset({"failed", "blocked", "challenge"})


@dataclass
class RateLimitDecision:
    allowed: bool
    wait_seconds: float
    reason: str


@dataclass
class RoundRobinState:
    """Estado em memória para round-robin de contas / proxies."""

    index: int = 0
    proxy_index: int = 0
    # Contagem de atribuições no dia de agendamento (schedule_campaign).
    day_assignments: dict[uuid.UUID, int] = field(default_factory=dict)


def effective_warmup_day(account: Account) -> int:
    """Dia de rampa efetivo (ver docstring do módulo)."""
    if account.warmup_day >= 1:
        return account.warmup_day
    if account.status == "warming":
        return 1
    return 4


def daily_cap_for_account(
    account: Account,
    *,
    settings: Settings | None = None,
) -> int:
    """Retorna o teto de DMs/sucesso por dia civil para a conta."""
    settings = settings or get_settings()
    max_daily = settings.antiban_max_dm_per_account_per_day
    if not settings.antiban_warmup_enabled:
        return max_daily
    day = effective_warmup_day(account)
    if day >= 4:
        return max_daily
    return min(WARMUP_CAPS.get(day, max_daily), max_daily)


def parse_proxy_urls(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    return [p.strip() for p in settings.proxy_urls.split(",") if p.strip()]


def count_successful_dms_on_utc_date(
    db: Session,
    account_id: uuid.UUID,
    day: date,
) -> int:
    """Conta mensagens ``success`` da conta num dia civil UTC."""
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    rows = db.scalars(
        select(Message).where(
            Message.account_id == account_id,
            Message.result == "success",
        )
    ).all()
    total = 0
    for msg in rows:
        ts = msg.sent_at if msg.sent_at is not None else msg.created_at
        if day_start <= _as_aware(ts) < day_end:
            total += 1
    return total


def count_successful_dms_today(
    db: Session,
    account_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    """Conta mensagens ``success`` da conta no dia civil UTC atual."""
    now = _as_aware(now or datetime.now(UTC))
    return count_successful_dms_on_utc_date(db, account_id, now.date())


def last_successful_send_at(
    db: Session,
    account_id: uuid.UUID,
) -> datetime | None:
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.account_id == account_id, Message.result == "success")
            .order_by(Message.created_at.desc())
            .limit(50)
        ).all()
    )
    best: datetime | None = None
    for row in rows:
        ts = row.sent_at if row.sent_at is not None else row.created_at
        aware = _as_aware(ts)
        if best is None or aware > best:
            best = aware
    return best


def check_rate_limit(
    db: Session,
    account_id: uuid.UUID,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    messages_today: int | None = None,
) -> RateLimitDecision:
    """Avalia cota diária (warm-up) + intervalo mínimo desde o último envio."""
    settings = settings or get_settings()
    now = _as_aware(now or datetime.now(UTC))

    account = db.get(Account, account_id)
    if account is None:
        return RateLimitDecision(allowed=False, wait_seconds=60.0, reason="account_not_found")

    if account.status not in ELIGIBLE_ACCOUNT_STATUSES:
        return RateLimitDecision(
            allowed=False,
            wait_seconds=300.0,
            reason=f"account_status_{account.status}",
        )

    # Rollover UTC: avança warm-up só quando o dia atual ainda não tem envios.
    maybe_advance_warmup(db, account, now=now, settings=settings)

    today_count = (
        messages_today
        if messages_today is not None
        else count_successful_dms_today(db, account_id, now=now)
    )
    cap = daily_cap_for_account(account, settings=settings)
    if today_count >= cap:
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait = max((tomorrow - now).total_seconds(), 60.0)
        return RateLimitDecision(
            allowed=False,
            wait_seconds=wait,
            reason=f"daily_cap_reached:{today_count}/{cap}",
        )

    min_delay = settings.antiban_min_delay_sec
    last_at = last_successful_send_at(db, account_id)
    if last_at is not None and min_delay > 0:
        elapsed = (now - last_at).total_seconds()
        if elapsed < min_delay:
            wait = float(min_delay - elapsed)
            return RateLimitDecision(
                allowed=False,
                wait_seconds=wait,
                reason=f"min_delay:{min_delay}s",
            )

    return RateLimitDecision(allowed=True, wait_seconds=0.0, reason="ok")


def random_inter_send_delay_seconds(
    *,
    settings: Settings | None = None,
    rng_uniform: float | None = None,
) -> float:
    """Delay aleatório entre ``min`` e ``max`` (útil em bursts do worker)."""
    import random

    settings = settings or get_settings()
    low = settings.antiban_min_delay_sec
    high = max(settings.antiban_max_delay_sec, low)
    if rng_uniform is not None:
        return low + (high - low) * rng_uniform
    return float(random.randint(low, high))


def next_account_round_robin(
    db: Session,
    account_ids: list[uuid.UUID] | None = None,
    *,
    state: RoundRobinState | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    respect_rate_limit: bool = True,
    day_caps: dict[uuid.UUID, int] | None = None,
) -> uuid.UUID | None:
    """Escolhe a próxima conta elegível (active|warming), pulando as no limite.

    Se ``account_ids`` for None, carrega todas as contas elegíveis do DB.
    Atribui proxy da pool ``proxy_urls`` quando a conta não tem proxy próprio
    (leve — só preenche ``Account.proxy`` se estiver vazio).
    """
    settings = settings or get_settings()
    state = state or RoundRobinState()
    now = _as_aware(now or datetime.now(UTC))

    if account_ids is None:
        accounts = list(
            db.scalars(
                select(Account)
                .where(Account.status.in_(ELIGIBLE_ACCOUNT_STATUSES))
                .order_by(Account.created_at.asc())
            ).all()
        )
    else:
        accounts = []
        for aid in account_ids:
            acc = db.get(Account, aid)
            if acc is not None and acc.status in ELIGIBLE_ACCOUNT_STATUSES:
                accounts.append(acc)

    if not accounts:
        return None

    n = len(accounts)
    proxies = parse_proxy_urls(settings)

    for offset in range(n):
        idx = (state.index + offset) % n
        account = accounts[idx]

        if day_caps is not None:
            used = state.day_assignments.get(account.id, 0)
            cap = day_caps.get(account.id, settings.antiban_max_dm_per_account_per_day)
            if used >= cap:
                continue

        if respect_rate_limit:
            decision = check_rate_limit(db, account.id, now=now, settings=settings)
            if not decision.allowed and decision.reason.startswith("daily_cap_reached"):
                continue
            # min_delay: ainda elegível para *agendar*; worker deferirá no envio.
            if not decision.allowed and decision.reason.startswith("account_status_"):
                continue

        state.index = idx + 1
        state.day_assignments[account.id] = state.day_assignments.get(account.id, 0) + 1
        _maybe_assign_proxy(account, proxies, state)
        return account.id

    # Todas no limite diário — devolve a próxima em RR puro (worker deferirá).
    account = accounts[state.index % n]
    state.index = (state.index % n) + 1
    state.day_assignments[account.id] = state.day_assignments.get(account.id, 0) + 1
    _maybe_assign_proxy(account, proxies, state)
    return account.id


def build_day_caps(
    accounts: list[Account],
    *,
    settings: Settings | None = None,
) -> dict[uuid.UUID, int]:
    settings = settings or get_settings()
    return {acc.id: daily_cap_for_account(acc, settings=settings) for acc in accounts}


def maybe_advance_warmup(
    db: Session,
    account: Account,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> bool:
    """Avança ``warmup_day`` só no rollover UTC após um dia que atingiu o cap.

    Nunca libera cota maior no mesmo dia civil (Dia 1 permanece em 20 DMs).
    """
    settings = settings or get_settings()
    if not settings.antiban_warmup_enabled:
        return False

    now = _as_aware(now or datetime.now(UTC))
    today_count = count_successful_dms_today(db, account.id, now=now)
    if today_count > 0:
        return False

    day = effective_warmup_day(account)
    if day >= 4 and account.status != "warming":
        return False

    cap = daily_cap_for_account(account, settings=settings)
    yesterday = now.date() - timedelta(days=1)
    yesterday_count = count_successful_dms_on_utc_date(db, account.id, yesterday)
    if yesterday_count < cap:
        return False

    new_day = max(account.warmup_day, day) + 1
    account.warmup_day = new_day
    if new_day >= 4 and account.status == "warming":
        account.status = "active"
        logger.info(
            "Warm-up concluído account=%s → active (warmup_day=%s)",
            account.id,
            new_day,
        )
    else:
        logger.info(
            "Warm-up avançado account=%s warmup_day=%s",
            account.id,
            new_day,
        )
    return True


def should_auto_pause(*, consecutive_failures: int, threshold: int = 5) -> bool:
    """Circuit breaker puro: N falhas consecutivas → pausa automática."""
    return consecutive_failures >= threshold


def count_consecutive_failures(db: Session, campaign_id: uuid.UUID) -> int:
    """Conta falhas recentes desde o último sucesso (persistente entre runs)."""
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.campaign_id == campaign_id)
            .order_by(Message.created_at.desc())
            .limit(100)
        ).all()
    )
    count = 0
    for msg in rows:
        if msg.result == "success":
            break
        if msg.result in FAILURE_RESULTS:
            count += 1
    return count


def trigger_auto_pause(
    db: Session,
    campaign: Campaign,
    *,
    reason: str,
    account_id: uuid.UUID | None = None,
) -> bool:
    """Marca campanha ``auto_paused``, cancela jobs pending e registra log ``pause``."""
    if campaign.status != "active":
        return False

    from services.logging.service import write_log
    from services.scheduler.service import cancel_pending_jobs

    campaign.status = "auto_paused"
    db.flush()
    cancelled = cancel_pending_jobs(db, campaign.id)
    write_log(
        db,
        action="pause",
        result="info",
        campaign_id=campaign.id,
        account_id=account_id,
        error=reason,
        details=f"auto_pause cancelled_jobs={cancelled}",
        commit=True,
    )
    logger.warning(
        "Campanha auto_paused id=%s reason=%s cancelled=%s",
        campaign.id,
        reason,
        cancelled,
    )
    return True


def account_antiban_status(
    db: Session,
    account: Account,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Snapshot para CLI / debugging."""
    settings = settings or get_settings()
    now = _as_aware(now or datetime.now(UTC))
    today = count_successful_dms_today(db, account.id, now=now)
    cap = daily_cap_for_account(account, settings=settings)
    decision = check_rate_limit(db, account.id, now=now, settings=settings, messages_today=today)
    return {
        "account_id": str(account.id),
        "username": account.username,
        "status": account.status,
        "warmup_day": account.warmup_day,
        "effective_warmup_day": effective_warmup_day(account),
        "messages_today": today,
        "daily_cap": cap,
        "remaining": max(cap - today, 0),
        "rate_limit_allowed": decision.allowed,
        "rate_limit_reason": decision.reason,
        "wait_seconds": decision.wait_seconds,
        "proxy": account.proxy,
    }


def _maybe_assign_proxy(
    account: Account,
    proxies: list[str],
    state: RoundRobinState,
) -> None:
    if account.proxy or not proxies:
        return
    account.proxy = proxies[state.proxy_index % len(proxies)]
    state.proxy_index += 1


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
