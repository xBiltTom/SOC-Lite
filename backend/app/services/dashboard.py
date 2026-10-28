"""Consultas de métricas del dashboard.

Las agregaciones se ejecutan en PostgreSQL (no en Python) para que el tablero
siga respondiendo con cientos de miles de alertas; `percentile_cont` calcula el
P95 del MTTT y las ventanas se parametrizan con `make_interval`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import Severity

_LATEST = """
latest AS (
    SELECT DISTINCT ON (tr.alert_id)
           tr.alert_id, tr.verdict, tr.severity AS triage_severity,
           tr.triaged_at, tr.needs_human, tr.fallback_used
    FROM triage_results tr
    ORDER BY tr.alert_id, tr.triaged_at DESC
)
"""

_TARGETS = {
    "critical": settings.sla_critical_minutes,
    "high": settings.sla_high_minutes,
    "medium": settings.sla_medium_minutes,
    "low": settings.sla_low_minutes,
    "info": settings.sla_low_minutes,
}


def _sla_case(alias: str = "a") -> str:
    return (
        f"CASE {alias}.severity "
        f"WHEN 'critical' THEN {settings.sla_critical_minutes} "
        f"WHEN 'high' THEN {settings.sla_high_minutes} "
        f"WHEN 'medium' THEN {settings.sla_medium_minutes} "
        f"ELSE {settings.sla_low_minutes} END"
    )


async def summary(db: AsyncSession, days: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    previous_start = start - timedelta(days=days)

    query = text(
        f"""
        WITH {_LATEST},
        base AS (
            SELECT a.*, l.verdict, l.triaged_at, l.needs_human
            FROM alerts a
            LEFT JOIN latest l ON l.alert_id = a.id
            WHERE a.received_at >= now() - make_interval(days => :days)
        )
        SELECT
            COUNT(*) AS alerts,
            COUNT(*) FILTER (WHERE severity = 'critical') AS critical,
            COUNT(*) FILTER (WHERE severity = 'high') AS high,
            COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
            COUNT(*) FILTER (WHERE severity = 'low') AS low,
            COUNT(*) FILTER (WHERE severity = 'info') AS info,
            COUNT(*) FILTER (WHERE triaged_at IS NOT NULL) AS triaged,
            COUNT(*) FILTER (WHERE status IN ('pending','triaging','triage_failed')) AS pending,
            COUNT(*) FILTER (WHERE verdict = 'false_positive') AS false_positive,
            COUNT(*) FILTER (WHERE needs_human) AS human_review,
            COALESCE(AVG(EXTRACT(EPOCH FROM (triaged_at - received_at)) / 60.0), 0) AS avg_minutes,
            COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (triaged_at - received_at)) / 60.0), 0) AS p95_minutes,
            COUNT(*) FILTER (
                WHERE triaged_at IS NOT NULL
                  AND EXTRACT(EPOCH FROM (triaged_at - received_at)) / 60.0 <= {_sla_case("base")}
            ) AS within_sla
        FROM base
        """
    )
    row = (await db.execute(query, {"days": days})).mappings().one()

    previous = text(
        """
        WITH latest AS (
            SELECT DISTINCT ON (tr.alert_id) tr.alert_id, tr.triaged_at
            FROM triage_results tr ORDER BY tr.alert_id, tr.triaged_at DESC
        )
        SELECT COUNT(*) AS alerts,
               COALESCE(AVG(EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0), 0) AS avg_minutes
        FROM alerts a LEFT JOIN latest l ON l.alert_id = a.id
        WHERE a.received_at >= now() - make_interval(days => :days2)
          AND a.received_at < now() - make_interval(days => :days)
        """
    )
    prev = (
        await db.execute(previous, {"days": days, "days2": days * 2})
    ).mappings().one()

    incidents_open = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM incidents WHERE opened_at >= now() - make_interval(days => :days) "
                "AND status IN ('open','investigating','contained')"
            ),
            {"days": days},
        )
    ).scalar_one()

    total = int(row["alerts"] or 0)
    triaged = int(row["triaged"] or 0)
    fp = int(row["false_positive"] or 0)

    def pct(part: float, whole: float) -> float:
        return round((part / whole) * 100, 1) if whole else 0.0

    def delta(current: float, old: float) -> float:
        if not old:
            return 0.0
        return round(((current - old) / old) * 100, 1)

    return {
        "period": {"days": days, "date_from": start.date(), "date_to": now.date()},
        "totals": {
            "alerts": total,
            "critical": int(row["critical"] or 0),
            "high": int(row["high"] or 0),
            "medium": int(row["medium"] or 0),
            "low": int(row["low"] or 0),
            "info": int(row["info"] or 0),
            "triaged": triaged,
            "pending": int(row["pending"] or 0),
            "incidents_open": int(incidents_open or 0),
            "false_positive": fp,
        },
        "rates": {
            "automation": pct(triaged, total),
            "false_positive": pct(fp, triaged),
            "sla_compliance": pct(int(row["within_sla"] or 0), triaged),
            "human_review": pct(int(row["human_review"] or 0), triaged),
        },
        "mttt": {
            "avg_minutes": round(float(row["avg_minutes"] or 0), 1),
            "p95_minutes": round(float(row["p95_minutes"] or 0), 1),
            "target_minutes": settings.sla_high_minutes,
        },
        "deltas": {
            "alerts_pct": delta(total, int(prev["alerts"] or 0)),
            "mttt_pct": delta(float(row["avg_minutes"] or 0), float(prev["avg_minutes"] or 0)),
        },
        "generated_at": now,
    }


async def trend(db: AsyncSession, days: int) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    query = text(
        f"""
        WITH {_LATEST}
        SELECT d::date AS date,
               COUNT(a.id) AS total,
               COUNT(a.id) FILTER (WHERE a.severity = 'critical') AS critical,
               COUNT(a.id) FILTER (WHERE a.severity = 'high') AS high,
               COUNT(a.id) FILTER (WHERE a.severity = 'medium') AS medium,
               COUNT(a.id) FILTER (WHERE a.severity = 'low') AS low,
               COUNT(a.id) FILTER (WHERE l.verdict = 'false_positive') AS false_positive
        FROM generate_series(CAST(:start AS date), CAST(:end AS date), interval '1 day') d
        LEFT JOIN alerts a ON a.received_at >= d AND a.received_at < d + interval '1 day'
        LEFT JOIN latest l ON l.alert_id = a.id
        GROUP BY d
        ORDER BY d
        """
    )
    rows = (await db.execute(query, {"start": start, "end": end})).mappings().all()
    return [
        {
            "date": row["date"],
            "total": int(row["total"] or 0),
            "critical": int(row["critical"] or 0),
            "high": int(row["high"] or 0),
            "medium": int(row["medium"] or 0),
            "low": int(row["low"] or 0),
            "false_positive": int(row["false_positive"] or 0),
        }
        for row in rows
    ]


async def severity_distribution(db: AsyncSession, days: int) -> dict[str, Any]:
    rows = (
        await db.execute(
            text(
                "SELECT severity, COUNT(*) AS count FROM alerts "
                "WHERE received_at >= now() - make_interval(days => :days) GROUP BY severity"
            ),
            {"days": days},
        )
    ).mappings().all()
    counts = {str(row["severity"]): int(row["count"]) for row in rows}
    items = [
        {"severity": severity.value, "count": counts.get(severity.value, 0)}
        for severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO)
    ]
    return {"items": items, "total": sum(counts.values())}


async def top_sources(db: AsyncSession, days: int, limit: int, by: str = "ip") -> list[dict[str, Any]]:
    column = {
        "ip": "COALESCE(host(a.src_ip), 'sin origen')",
        "agent": "COALESCE(a.agent_name, 'sin agente')",
        "rule": "COALESCE(a.rule_id, 'sin regla')",
    }.get(by, "COALESCE(host(a.src_ip), 'sin origen')")
    query = text(
        f"""
        SELECT {column} AS label,
               COUNT(*) AS count,
               COUNT(*) FILTER (WHERE a.severity IN ('critical','high')) AS critical
        FROM alerts a
        WHERE a.received_at >= now() - make_interval(days => :days)
        GROUP BY 1
        ORDER BY count DESC
        LIMIT :limit
        """
    )
    rows = (await db.execute(query, {"days": days, "limit": limit})).mappings().all()
    return [
        {
            "key": str(row["label"]),
            "label": str(row["label"]),
            "count": int(row["count"]),
            "critical": int(row["critical"] or 0),
        }
        for row in rows
    ]


async def mttt_by_severity(db: AsyncSession, days: int) -> list[dict[str, Any]]:
    query = text(
        f"""
        WITH {_LATEST}
        SELECT a.severity,
               COUNT(*) AS count,
               ROUND(AVG(EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0)::numeric, 1) AS avg_minutes,
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
                     ORDER BY EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0)::numeric, 1) AS p95_minutes,
               COUNT(*) FILTER (
                   WHERE EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0 <= {_sla_case()}
               ) AS within_sla
        FROM alerts a
        JOIN latest l ON l.alert_id = a.id
        WHERE a.received_at >= now() - make_interval(days => :days)
        GROUP BY a.severity
        """
    )
    rows = (await db.execute(query, {"days": days})).mappings().all()
    data = {
        str(row["severity"]): {
            "severity": str(row["severity"]),
            "count": int(row["count"]),
            "avg_minutes": float(row["avg_minutes"] or 0),
            "p95_minutes": float(row["p95_minutes"] or 0),
            "target_minutes": _TARGETS[str(row["severity"])],
            "compliance": round((int(row["within_sla"] or 0) / int(row["count"])) * 100, 1)
            if row["count"]
            else 0.0,
        }
        for row in rows
    }
    return [
        data.get(
            severity.value,
            {
                "severity": severity.value,
                "count": 0,
                "avg_minutes": 0.0,
                "p95_minutes": 0.0,
                "target_minutes": _TARGETS[severity.value],
                "compliance": 0.0,
            },
        )
        for severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)
    ]


async def fp_series(db: AsyncSession, days: int) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    query = text(
        f"""
        WITH {_LATEST}
        SELECT d::date AS date,
               COUNT(l.alert_id) AS triaged,
               COUNT(l.alert_id) FILTER (WHERE l.verdict = 'false_positive') AS false_positive
        FROM generate_series(CAST(:start AS date), CAST(:end AS date), interval '1 day') d
        LEFT JOIN alerts a ON a.received_at >= d AND a.received_at < d + interval '1 day'
        LEFT JOIN latest l ON l.alert_id = a.id
        GROUP BY d ORDER BY d
        """
    )
    rows = (await db.execute(query, {"start": start, "end": end})).mappings().all()
    return [
        {
            "date": row["date"],
            "triaged": int(row["triaged"] or 0),
            "false_positive": int(row["false_positive"] or 0),
            "rate": round((int(row["false_positive"] or 0) / int(row["triaged"])) * 100, 1)
            if row["triaged"]
            else 0.0,
        }
        for row in rows
    ]


async def sla_rows(db: AsyncSession, days: int) -> list[dict[str, Any]]:
    rows = await mttt_by_severity(db, days)
    result = []
    for row in rows:
        breaches = row["count"] - round(row["count"] * row["compliance"] / 100)
        result.append(
            {
                "severity": row["severity"],
                "target_minutes": row["target_minutes"],
                "total": row["count"],
                "within_sla": round(row["count"] * row["compliance"] / 100),
                "compliance": row["compliance"],
                "breaches": max(breaches, 0),
            }
        )
    return result


async def analyst_activity(db: AsyncSession, days: int) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT u.username, u.full_name,
               COUNT(a.id) FILTER (WHERE a.action NOT IN ('ENTER','EXIT')) AS actions,
               COUNT(a.id) FILTER (WHERE a.action = 'TRIAGE_RUN') AS triages
        FROM users u
        LEFT JOIN audit_log a ON a.user_id = u.id
             AND a.occurred_at >= now() - make_interval(days => :days)
        WHERE u.deleted_at IS NULL
        GROUP BY u.id, u.username, u.full_name
        ORDER BY actions DESC
        LIMIT 10
        """
    )
    rows = (await db.execute(query, {"days": days})).mappings().all()
    return [
        {
            "username": row["username"],
            "full_name": row["full_name"],
            "actions": int(row["actions"] or 0),
            "triages": int(row["triages"] or 0),
        }
        for row in rows
    ]
