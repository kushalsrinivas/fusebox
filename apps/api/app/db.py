"""Storage abstraction.

Phase 0: Postgres when DATABASE_URL is set, else process-local memory.
This keeps `pytest` and local demo working without docker, while the
migration in ../migrations/001_init.sql remains the source of truth.
"""

import uuid
from datetime import datetime, timezone

from .config import DATABASE_URL

_mem: dict[str, list[dict]] = {}
_mem_deploys: dict[str, list[dict]] = {}
_mem_groups: dict[tuple[str, str], dict] = {}
_mem_occ: dict[tuple[str, str], list[dict]] = {}
_mem_clusters: dict[str, list[dict]] = {}
_mem_investigations: dict[str, list[dict]] = {}
_mem_actions: dict[str, list[dict]] = {}
_mem_verifications: dict[str, list[dict]] = {}
_mem_signals: dict[str, list[dict]] = {}
_mem_usage: dict[tuple[str, str], int] = {}
_mem_audit: list[dict] = []
_mem_plans: dict[str, str] = {}

# Memory cap per error group: persist-the-tail sampling (arch §4.6).
# Postgres path keeps full history + scheduled 90d delete (see 002 migration).
MAX_OCCURRENCES_MEM = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_feedback(tenant_id: str, payload: dict) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "source": payload.get("source", "api"),
        "type": payload.get("type", "other"),
        "title": payload["title"],
        "body": payload.get("body", ""),
        "app_version": payload.get("app_version"),
        "os": payload.get("os"),
        "service_hint": payload.get("service_hint"),
        "external_id": payload.get("external_id"),
        "occurred_at": payload.get("occurred_at") or _now(),
        "created_at": _now(),
    }
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into feedback
                      (id, tenant_id, source, type, title, body, app_version, os, service_hint, external_id, occurred_at)
                    values
                      (%(id)s, %(tenant_id)s, %(source)s, %(type)s, %(title)s, %(body)s,
                       %(app_version)s, %(os)s, %(service_hint)s, %(external_id)s, %(occurred_at)s)
                    """,
                    row,
                )
            conn.commit()
    else:
        _mem.setdefault(tenant_id, []).append(row)
    return row


def list_feedback(tenant_id: str, limit: int = 50) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # RLS note: production callers set app.tenant_id; the service role
                # path below is additionally filtered by tenant_id (defense in depth).
                cur.execute(
                    "select * from feedback where tenant_id = %s order by created_at desc limit %s",
                    (tenant_id, limit),
                )
                return list(cur.fetchall())
    rows = sorted(_mem.get(tenant_id, []), key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]


def clear_memory() -> None:
    _mem.clear()
    _mem_deploys.clear()
    _mem_groups.clear()
    _mem_occ.clear()
    _mem_clusters.clear()
    _mem_investigations.clear()
    _mem_actions.clear()
    _mem_verifications.clear()
    _mem_signals.clear()
    _mem_usage.clear()
    _mem_audit.clear()
    _mem_plans.clear()


# --- Deployments ------------------------------------------------------------

def save_deployment(tenant_id: str, payload: dict) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "service": payload["service"],
        "version": payload.get("version", ""),
        "commit_sha": payload.get("commit_sha"),
        "env": payload.get("env", "production"),
        "deployed_at": payload.get("deployed_at") or _now(),
        "created_at": _now(),
    }
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into deployments
                      (id, tenant_id, service, version, commit_sha, env, deployed_at)
                    values
                      (%(id)s, %(tenant_id)s, %(service)s, %(version)s,
                       %(commit_sha)s, %(env)s, %(deployed_at)s)
                    """,
                    row,
                )
            conn.commit()
    else:
        _mem_deploys.setdefault(tenant_id, []).append(row)
    return row


def list_deployments(tenant_id: str, service: str | None = None,
                     limit: int = 50) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if service:
                    cur.execute(
                        "select * from deployments where tenant_id = %s and service = %s"
                        " order by deployed_at desc limit %s",
                        (tenant_id, service, limit),
                    )
                else:
                    cur.execute(
                        "select * from deployments where tenant_id = %s"
                        " order by deployed_at desc limit %s",
                        (tenant_id, limit),
                    )
                return list(cur.fetchall())
    rows = _mem_deploys.get(tenant_id, [])
    if service:
        rows = [r for r in rows if r["service"] == service]
    return sorted(rows, key=lambda r: r["deployed_at"], reverse=True)[:limit]


# --- Error groups + occurrences ----------------------------------------------

def record_error(tenant_id: str, payload: dict) -> dict:
    """Upsert group by fingerprint, append one (sampled) occurrence."""
    fp = payload["fingerprint"]
    now = _now()
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    insert into error_groups
                      (tenant_id, fingerprint, service, release, title, first_seen, last_seen, count)
                    values (%s, %s, %s, %s, %s, %s, %s, 1)
                    on conflict (tenant_id, fingerprint) do update set
                      last_seen = excluded.last_seen,
                      count = error_groups.count + 1,
                      title = case when error_groups.title = '' then excluded.title
                                   else error_groups.title end
                    returning *
                    """,
                    (tenant_id, fp, payload.get("service", "unknown"),
                     payload.get("release"), payload.get("title", ""),
                     payload.get("ts") or now, payload.get("ts") or now),
                )
                group = dict(cur.fetchone())
                cur.execute(
                    """
                    insert into error_occurrences
                      (tenant_id, fingerprint, service, level, message, event_id, ts)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (tenant_id, fp, payload.get("service", "unknown"),
                     payload.get("level", "error"), payload.get("message", "")[:2000],
                     payload.get("event_id"), payload.get("ts") or now),
                )
            conn.commit()
        return group
    key = (tenant_id, fp)
    group = _mem_groups.get(key)
    if group is None:
        group = {
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "fingerprint": fp,
            "service": payload.get("service", "unknown"), "release": payload.get("release"),
            "title": payload.get("title", ""), "first_seen": payload.get("ts") or now,
            "last_seen": payload.get("ts") or now, "count": 0,
        }
        _mem_groups[key] = group
    group["count"] += 1
    group["last_seen"] = payload.get("ts") or now
    if not group["title"] and payload.get("title"):
        group["title"] = payload["title"]
    occ = _mem_occ.setdefault(key, [])
    occ.append({"service": group["service"], "level": payload.get("level", "error"),
                "message": payload.get("message", "")[:2000],
                "event_id": payload.get("event_id"), "ts": payload.get("ts") or now})
    del occ[:-MAX_OCCURRENCES_MEM]
    return group


def list_error_groups(tenant_id: str, service: str | None = None,
                      limit: int = 50) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if service:
                    cur.execute(
                        "select * from error_groups where tenant_id = %s and service = %s"
                        " order by last_seen desc limit %s",
                        (tenant_id, service, limit),
                    )
                else:
                    cur.execute(
                        "select * from error_groups where tenant_id = %s"
                        " order by last_seen desc limit %s",
                        (tenant_id, limit),
                    )
                return list(cur.fetchall())
    groups = [g for (t, _), g in _mem_groups.items() if t == tenant_id]
    if service:
        groups = [g for g in groups if g["service"] == service]
    return sorted(groups, key=lambda g: g["last_seen"], reverse=True)[:limit]


# --- Clusters + investigations (Phase 3) --------------------------------------

def replace_clusters(tenant_id: str, clusters: list[dict]) -> list[dict]:
    rows = [{
        "id": str(uuid.uuid4()), "tenant_id": tenant_id, "key": c["key"],
        "title": c["title"], "count": c["count"],
        "service_hint": c.get("service_hint"), "status": c.get("status", "auto"),
        "member_ids": c["members"], "created_at": _now(),
    } for c in clusters]
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from issue_clusters where tenant_id = %s", (tenant_id,))
                for r in rows:
                    cur.execute(
                        """
                        insert into issue_clusters
                          (id, tenant_id, key, title, count, service_hint, status, member_ids)
                        values
                          (%(id)s, %(tenant_id)s, %(key)s, %(title)s, %(count)s,
                           %(service_hint)s, %(status)s, %(member_ids)s)
                        """,
                        r,
                    )
            conn.commit()
    else:
        _mem_clusters[tenant_id] = rows
    return rows


def list_clusters(tenant_id: str) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from issue_clusters where tenant_id = %s order by count desc",
                    (tenant_id,),
                )
                return [dict(r) for r in cur.fetchall()]
    return sorted(_mem_clusters.get(tenant_id, []), key=lambda r: r["count"], reverse=True)


def get_cluster(tenant_id: str, cid: str) -> dict | None:
    for r in list_clusters(tenant_id):
        if r["id"] == cid or r["key"] == cid:
            return r
    return None


def list_feedback_by_ids(tenant_id: str, ids: list[str]) -> list[dict]:
    want = set(ids)
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from feedback where tenant_id = %s and id = any(%s)",
                    (tenant_id, list(want)),
                )
                return [dict(r) for r in cur.fetchall()]
    return [r for r in _mem.get(tenant_id, []) if r["id"] in want]


def save_investigation(tenant_id: str, cluster_id: str, result: dict) -> dict:
    row = {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id, "cluster_id": cluster_id,
        "status": result.get("status", "needs_info"),
        "severity": result.get("severity", 2),
        "confidence": result.get("confidence", 0.3),
        "result": result, "created_at": _now(),
    }
    if DATABASE_URL:
        import json

        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into investigations
                      (id, tenant_id, cluster_id, status, severity, confidence, result)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (row["id"], tenant_id, cluster_id, row["status"],
                     row["severity"], row["confidence"], json.dumps(result)),
                )
            conn.commit()
    else:
        _mem_investigations.setdefault(tenant_id, []).append(row)
    return row


def latest_investigation(tenant_id: str, cluster_id: str) -> dict | None:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from investigations where tenant_id = %s and cluster_id = %s"
                    " order by created_at desc limit 1",
                    (tenant_id, cluster_id),
                )
                r = cur.fetchone()
                return dict(r) if r else None
    cands = [r for r in _mem_investigations.get(tenant_id, []) if r["cluster_id"] == cluster_id]
    return sorted(cands, key=lambda r: r["created_at"], reverse=True)[0] if cands else None


# --- Actions (Phase 4) ----------------------------------------------------------

def save_action(tenant_id: str, payload: dict) -> dict:
    import json as _json

    row = {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "cluster_id": payload.get("cluster_id"),
        "investigation_id": payload.get("investigation_id"),
        "repo": payload.get("repo", ""), "branch": payload.get("branch", ""),
        "title": payload.get("title", ""), "diff": payload.get("diff", ""),
        "status": payload.get("status", "proposed"),
        "risk": payload.get("risk", {}), "sandbox": payload.get("sandbox", {}),
        "pr_url": payload.get("pr_url"), "dry_run": payload.get("dry_run", True),
        "created_at": _now(),
    }
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into actions
                      (id, tenant_id, cluster_id, investigation_id, repo, branch,
                       title, diff, status, risk, sandbox, pr_url, dry_run)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (row["id"], tenant_id, row["cluster_id"], row["investigation_id"],
                     row["repo"], row["branch"], row["title"], row["diff"],
                     row["status"], _json.dumps(row["risk"]), _json.dumps(row["sandbox"]),
                     row["pr_url"], row["dry_run"]),
                )
            conn.commit()
    else:
        _mem_actions.setdefault(tenant_id, []).append(row)
    return row


def get_action(tenant_id: str, aid: str) -> dict | None:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from actions where tenant_id = %s and id = %s",
                    (tenant_id, aid),
                )
                r = cur.fetchone()
                return dict(r) if r else None
    for r in _mem_actions.get(tenant_id, []):
        if r["id"] == aid:
            return r
    return None


def list_actions(tenant_id: str, cluster_id: str | None = None) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if cluster_id:
                    cur.execute(
                        "select * from actions where tenant_id = %s and cluster_id = %s"
                        " order by created_at desc",
                        (tenant_id, cluster_id),
                    )
                else:
                    cur.execute(
                        "select * from actions where tenant_id = %s order by created_at desc",
                        (tenant_id,),
                    )
                return [dict(r) for r in cur.fetchall()]
    rows = _mem_actions.get(tenant_id, [])
    if cluster_id:
        rows = [r for r in rows if r["cluster_id"] == cluster_id]
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def update_action(tenant_id: str, aid: str, patch: dict) -> dict | None:
    if DATABASE_URL:
        import json as _json

        import psycopg
        from psycopg.rows import dict_row

        sets = ", ".join(f"{k} = %s" for k in patch)
        vals = [(_json.dumps(v) if isinstance(v, (dict, list)) else v)
                for v in patch.values()]
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"update actions set {sets} where tenant_id = %s and id = %s returning *",
                    (*vals, tenant_id, aid),
                )
                r = cur.fetchone()
            conn.commit()
            return dict(r) if r else None
    row = get_action(tenant_id, aid)
    if row is not None:
        row.update(patch)
    return row


# --- Occurrences / verifications / signals (Phase 5) ----------------------------

def count_occurrences(tenant_id: str, fingerprint: str,
                      since: str | None = None, until: str | None = None) -> int:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                q = ("select count(*) from error_occurrences "
                     "where tenant_id = %s and fingerprint = %s")
                args: list = [tenant_id, fingerprint]
                if since:
                    q += " and ts >= %s"
                    args.append(since)
                if until:
                    q += " and ts < %s"
                    args.append(until)
                cur.execute(q, args)
                return cur.fetchone()[0]
    occ = _mem_occ.get((tenant_id, fingerprint), [])
    return sum(1 for o in occ
               if (since is None or o["ts"] >= since) and (until is None or o["ts"] < until))


def save_verification(tenant_id: str, action_id: str, status: str, result: dict) -> dict:
    import json as _json

    row = {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "action_id": action_id,
           "status": status, "result": result, "checked_at": _now()}
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into verifications (id, tenant_id, action_id, status, result)"
                    " values (%s, %s, %s, %s, %s)",
                    (row["id"], tenant_id, action_id, status, _json.dumps(result)),
                )
            conn.commit()
    else:
        _mem_verifications.setdefault(tenant_id, []).append(row)
    return row


def list_verifications(tenant_id: str, action_id: str | None = None) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if action_id:
                    cur.execute(
                        "select * from verifications where tenant_id = %s and action_id = %s"
                        " order by checked_at desc",
                        (tenant_id, action_id),
                    )
                else:
                    cur.execute(
                        "select * from verifications where tenant_id = %s order by checked_at desc",
                        (tenant_id,),
                    )
                return [dict(r) for r in cur.fetchall()]
    rows = _mem_verifications.get(tenant_id, [])
    if action_id:
        rows = [r for r in rows if r["action_id"] == action_id]
    return sorted(rows, key=lambda r: r["checked_at"], reverse=True)


VALID_SIGNALS = {"helpful", "wrong_cause", "wrong_fix", "not_useful"}


def save_signal(tenant_id: str, investigation_id: str | None,
                signal: str, note: str = "") -> dict:
    if signal not in VALID_SIGNALS:
        raise ValueError(f"unknown signal {signal!r}; want one of {sorted(VALID_SIGNALS)}")
    row = {"id": str(uuid.uuid4()), "tenant_id": tenant_id,
           "investigation_id": investigation_id, "signal": signal,
           "note": note[:2000], "created_at": _now()}
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into signals (id, tenant_id, investigation_id, signal, note)"
                    " values (%s, %s, %s, %s, %s)",
                    (row["id"], tenant_id, investigation_id, signal, row["note"]),
                )
            conn.commit()
    else:
        _mem_signals.setdefault(tenant_id, []).append(row)
    return row


def signal_summary(tenant_id: str) -> dict:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select signal, count(*) from signals where tenant_id = %s group by signal",
                    (tenant_id,),
                )
                return {s: n for s, n in cur.fetchall()}
    counts: dict[str, int] = {}
    for r in _mem_signals.get(tenant_id, []):
        counts[r["signal"]] = counts.get(r["signal"], 0) + 1
    return counts


# --- Plans, usage, audit (Phase 6) ------------------------------------------------

def get_plan(tenant_id: str) -> str:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("select plan from tenants where id = %s", (tenant_id,))
                r = cur.fetchone()
                return r[0] if r else "free"
    return _mem_plans.get(tenant_id, "free")


def set_plan(tenant_id: str, plan: str) -> str:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into tenants (id, name, plan) values (%s, %s, %s)"
                    " on conflict (id) do update set plan = excluded.plan",
                    (tenant_id, tenant_id[:8], plan),
                )
            conn.commit()
    else:
        _mem_plans[tenant_id] = plan
    return plan


def usage_used(tenant_id: str, kind: str) -> int:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select used from usage_counters where tenant_id = %s and kind = %s",
                    (tenant_id, kind),
                )
                r = cur.fetchone()
                return r[0] if r else 0
    return _mem_usage.get((tenant_id, kind), 0)


def usage_bump(tenant_id: str, kind: str, n: int = 1) -> int:
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into usage_counters (tenant_id, kind, used, updated_at)"
                    " values (%s, %s, %s, now())"
                    " on conflict (tenant_id, kind) do update set"
                    " used = usage_counters.used + excluded.used, updated_at = now()"
                    " returning used",
                    (tenant_id, kind, n),
                )
                used = cur.fetchone()[0]
            conn.commit()
        return used
    _mem_usage[(tenant_id, kind)] = _mem_usage.get((tenant_id, kind), 0) + n
    return _mem_usage[(tenant_id, kind)]


def log_audit(tenant_id: str | None, actor: str, action: str, args: dict | None = None) -> dict:
    import json as _json

    row = {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "actor": actor,
           "action": action, "args": args or {}, "created_at": _now()}
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into audit_log (id, tenant_id, actor, action, args)"
                    " values (%s, %s, %s, %s, %s)",
                    (row["id"], tenant_id, actor, action, _json.dumps(row["args"])),
                )
            conn.commit()
    else:
        _mem_audit.append(row)
    return row


def purge_tenant(tenant_id: str) -> dict:
    tables = ["audit_log", "signals", "verifications", "actions", "investigations",
              "issue_clusters", "error_occurrences", "error_groups", "deployments",
              "usage_counters", "connectors", "projects", "feedback"]
    removed: dict[str, int] = {}
    if DATABASE_URL:
        import psycopg

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                for t in tables:
                    cur.execute(f"delete from {t} where tenant_id = %s", (tenant_id,))
                    removed[t] = cur.rowcount
                cur.execute("delete from tenants where id = %s", (tenant_id,))
                removed["tenants"] = cur.rowcount
            conn.commit()
    else:
        before = {
            "feedback": sum(len(v) for v in _mem.values()),
        }
        for store in (_mem, _mem_deploys):
            store.pop(tenant_id, None)
        for key in [k for k in _mem_groups if k[0] == tenant_id]:
            _mem_groups.pop(key)
        for key in [k for k in _mem_occ if k[0] == tenant_id]:
            _mem_occ.pop(key)
        for store in (_mem_clusters, _mem_investigations, _mem_actions,
                      _mem_verifications, _mem_signals):
            store.pop(tenant_id, None)
        for key in [k for k in _mem_usage if k[0] == tenant_id]:
            _mem_usage.pop(key)
        _mem_plans.pop(tenant_id, None)
        removed["memory_stores"] = before["feedback"]
    log_audit(None, "system", "tenant_purged", {"tenant_id": tenant_id, "removed": removed})
    return removed


def list_audit(tenant_id: str, limit: int = 50) -> list[dict]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from audit_log where tenant_id = %s order by created_at desc limit %s",
                    (tenant_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]
    rows = [r for r in _mem_audit if r["tenant_id"] == tenant_id]
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:limit]
