"""Helpers puros de geração de slots para o scheduler de campanhas.

Sem DB / rede — seguro para testes unitários com RNG seedado.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, time, timedelta, timezone


def window_duration_seconds(window_start: time, window_end: time) -> int:
    """Retorna a duração útil da janela em segundos (mesmo dia civil)."""
    start = datetime.combine(date.min, window_start)
    end = datetime.combine(date.min, window_end)
    return max(int((end - start).total_seconds()), 0)


def generate_day_slots(
    day: date,
    count: int,
    window_start: time,
    window_end: time,
    min_interval_sec: int,
    max_interval_sec: int,
    *,
    rng: random.Random | None = None,
    tz: timezone = UTC,
) -> list[datetime]:
    """Gera ``count`` timestamps de envio dentro de ``window_start``–``window_end`` em ``day``.

    Slots consecutivos são separados por um intervalo aleatório em
    ``[min_interval_sec, max_interval_sec]`` quando a janela permite.
    Se ``(count - 1) * min_interval_sec`` exceder a janela, os intervalos são
    comprimidos uniformemente para que todos os slots caibam na janela.
    """
    if count <= 0:
        return []
    if window_start >= window_end:
        raise ValueError("window_start deve ser anterior a window_end")
    if min_interval_sec > max_interval_sec:
        raise ValueError("min_interval_sec deve ser <= max_interval_sec")

    rng = rng or random.Random()
    start_dt = datetime.combine(day, window_start, tzinfo=tz)
    window_sec = window_duration_seconds(window_start, window_end)

    if count == 1:
        offset = rng.randint(0, window_sec) if window_sec > 0 else 0
        return [start_dt + timedelta(seconds=offset)]

    gaps = count - 1
    min_span = gaps * min_interval_sec

    if min_span > window_sec:
        # Comprime uniformemente para caber todos os slots.
        step = window_sec / gaps
        return [start_dt + timedelta(seconds=int(round(i * step))) for i in range(count)]

    intervals = [rng.randint(min_interval_sec, max_interval_sec) for _ in range(gaps)]
    total = sum(intervals)

    # start_offset + sum(intervals) deve ser <= window_sec
    if total > window_sec:
        scale = window_sec / total
        intervals = [max(min_interval_sec, int(i * scale)) for i in intervals]
        # Corrige overflow residual de arredondamento / clamp no mínimo.
        while sum(intervals) > window_sec and any(i > min_interval_sec for i in intervals):
            for idx in range(len(intervals)):
                if intervals[idx] > min_interval_sec and sum(intervals) > window_sec:
                    intervals[idx] -= 1
        if sum(intervals) > window_sec:
            # Último recurso: espaçamento uniforme dentro da janela.
            step = window_sec / gaps
            return [start_dt + timedelta(seconds=int(round(i * step))) for i in range(count)]

    remaining_slack = window_sec - sum(intervals)
    start_offset = rng.randint(0, remaining_slack) if remaining_slack > 0 else 0

    slots: list[datetime] = []
    cursor = start_offset
    slots.append(start_dt + timedelta(seconds=cursor))
    for gap in intervals:
        cursor += gap
        slots.append(start_dt + timedelta(seconds=cursor))
    return slots


def clamp_time_to_window(
    when: datetime,
    window_start: time,
    window_end: time,
) -> datetime:
    """Mantém a data de ``when``, mas limita o horário ao intervalo da campanha."""
    day = when.date()
    tz = when.tzinfo or UTC
    start_dt = datetime.combine(day, window_start, tzinfo=tz)
    end_dt = datetime.combine(day, window_end, tzinfo=tz)
    clock = when.replace(tzinfo=tz)
    if clock < start_dt:
        return start_dt
    if clock > end_dt:
        return end_dt
    return clock


def followup_at(
    base: datetime,
    *,
    days_offset: int,
    window_start: time,
    window_end: time,
) -> datetime:
    """Agenda follow-up em base + days_offset, mesmo horário limitado à janela."""
    target = base + timedelta(days=days_offset)
    return clamp_time_to_window(target, window_start, window_end)
