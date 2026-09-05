"""Guards the RLS contract across migrations without needing a live DB."""

from pathlib import Path

MIG = Path(__file__).parent.parent / "migrations"

SQL1 = (MIG / "001_init.sql").read_text()


def test_rls_enabled():
    assert "enable row level security" in SQL1.lower()


def test_policy_scopes_tenant():
    assert "app.tenant_id" in SQL1
    assert "tenant_id" in SQL1


def test_feedback_has_tenant_index():
    assert "feedback_tenant_created_idx" in SQL1


# Every tenant-scoped table created after 001 must ship its own policy.
TABLE_MIGRATION = {
    "deployments": "002_observability.sql",
    "error_groups": "002_observability.sql",
    "error_occurrences": "002_observability.sql",
    "issue_clusters": "003_clusters.sql",
    "investigations": "003_clusters.sql",
    "actions": "004_actions.sql",
    "verifications": "005_verification.sql",
    "signals": "005_verification.sql",
    "usage_counters": "006_billing.sql",
    "audit_log": "006_billing.sql",
}


def test_all_tenant_tables_have_rls_policies():
    for table, migration in TABLE_MIGRATION.items():
        sql = (MIG / migration).read_text()
        assert f"enable row level security" in sql.lower(), migration
        assert f"{table}_tenant_isolation" in sql, f"{table} in {migration}"
        assert "app.tenant_id" in sql, migration
