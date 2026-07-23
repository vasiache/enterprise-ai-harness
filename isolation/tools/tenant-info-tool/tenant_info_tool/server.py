"""tenant-info-tool - per-tenant MCP tool.

Deployed once per tenant namespace; reads platform.tenants and platform.orgs
via TenantDB (RLS-scoped to TENANT_ID).

Tools:
    get_tenant_info()  → {id, display_name, plan, created_at, orgs: [{id, display_name}]}
    get_org_info(org_id) → {tenant_id, id, display_name}

Environment variables (set by Helm / Agent CRD deployment.env):
    TENANT_ID       - tenant short id (e.g. "alpha")
    DATABASE_URL    - postgres connection string for platform DB
    ORG             - org name (optional, for logging)
    AGENT_NAME      - agent name (optional, for logging)
    KAGENT_URL      - kagent controller URL (optional)
"""

from __future__ import annotations

from saas_common.mcp_base import create_server, get_db, get_tenant_id

mcp = create_server("tenant-info-tool")


@mcp.tool()
async def get_tenant_info() -> dict:
    """Return metadata about the current tenant including its organisations.

    Reads platform.tenants and platform.orgs via TenantDB (RLS-scoped to TENANT_ID).

    Returns:
        id: tenant short id
        display_name: human-readable name
        plan: subscription plan (free / starter / pro)
        created_at: ISO 8601 timestamp
        orgs: list of {id, display_name} for all orgs of this tenant
        found: whether the tenant row exists in the database
    """
    tid = get_tenant_id()
    db = get_db()

    row = await db.query_one(
        "SELECT id, display_name, plan, created_at FROM platform.tenants WHERE id = $1",
        [tid],
        tenant_id=tid,
    )

    if row is None:
        return {
            "id": tid,
            "display_name": None,
            "plan": None,
            "created_at": None,
            "orgs": [],
            "found": False,
        }

    orgs = await db.query(
        "SELECT id, display_name FROM platform.orgs WHERE tenant_id = $1 ORDER BY id",
        [tid],
        tenant_id=tid,
    )

    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "plan": row["plan"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "orgs": [{"id": o["id"], "display_name": o["display_name"]} for o in orgs],
        "found": True,
    }


@mcp.tool()
async def get_org_info(org_id: str) -> dict:
    """Return metadata about a specific organisation within the current tenant.

    Args:
        org_id: organisation id (e.g. 'sales', 'management', 'default')

    Returns:
        tenant_id: parent tenant id
        id: org id
        display_name: human-readable org name
        found: whether the org row exists
    """
    tid = get_tenant_id()
    db = get_db()

    row = await db.query_one(
        "SELECT tenant_id, id, display_name FROM platform.orgs"
        " WHERE tenant_id = $1 AND id = $2",
        [tid, org_id],
        tenant_id=tid,
    )

    if row is None:
        return {"tenant_id": tid, "id": org_id, "display_name": None, "found": False}

    return {
        "tenant_id": row["tenant_id"],
        "id": row["id"],
        "display_name": row["display_name"],
        "found": True,
    }


def main() -> None:
    import uvicorn

    app = mcp.http_app(path="/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
