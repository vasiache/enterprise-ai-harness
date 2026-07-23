"""order-tracker - per-tenant MCP tool.

Deployed once per tenant namespace; manages leads and order lifecycle
via orders.leads (RLS-scoped to TENANT_ID).

Tools:
    create_lead(customer_tg_id, product, price)
        → create a new lead, returns lead id

    update_lead_status(lead_id, status, sold_at)
        → update lead status: new → qualified → sold / lost

    get_leads(status, limit)
        → list leads for the current tenant, optionally filtered by status

    get_lead_stats()
        → summary counts and total commission for the tenant

Environment variables (set by Helm):
    TENANT_ID           - tenant short id (e.g. "alpha")
    DATABASE_URL        - postgres connection string

Lead statuses:
    'new'        - initial state after customer expresses interest
    'qualified'  - needs confirmed, price discussed
    'sold'       - purchase completed (commission is calculated)
    'lost'       - customer declined or went cold
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from saas_common.mcp_base import create_server, get_db, get_tenant_id

logger = logging.getLogger(__name__)

mcp = create_server("order-tracker")

VALID_STATUSES = ("new", "qualified", "sold", "lost")

ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new":       ("qualified", "lost"),
    "qualified": ("sold",      "lost"),
    "sold":      (),
    "lost":      (),
}


@mcp.tool()
async def create_lead(
    product: str,
    price: float,
    customer_tg_id: int | None = None,
) -> dict:
    """Create a new sales lead.

    Args:
        product:        Product or service name the customer is interested in.
        price:          Asking price (used to calculate 5% commission on sale).
        customer_tg_id: Telegram user ID of the customer (optional).

    Returns:
        id:         UUID of the created lead.
        tenant_id:  Current tenant.
        product:    Echoed back.
        price:      Echoed back.
        status:     Always 'new'.
        commission_amount: Calculated commission (price × 0.05).
    """
    tid = get_tenant_id()
    db = get_db()

    row = await db.query_one(
        """
        INSERT INTO orders.leads (tenant_id, customer_tg_id, product, price)
        VALUES ($1, $2, $3, $4)
        RETURNING id, tenant_id, product, price, status, commission_amount, created_at
        """,
        [tid, customer_tg_id, product, price],
        tenant_id=tid,
    )

    logger.info("Created lead id=%s tenant=%s product=%s", row["id"], tid, product)
    return _lead_to_dict(row)


@mcp.tool()
async def update_lead_status(
    lead_id: str,
    status: str,
) -> dict:
    """Update the status of a lead.

    Valid transitions:
        new → qualified → sold
        any → lost

    Args:
        lead_id: UUID of the lead to update.
        status:  New status: 'new', 'qualified', 'sold', or 'lost'.

    Returns:
        Updated lead dict, or {'error': '...'} if not found or invalid status.
    """
    if status not in VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {VALID_STATUSES}"}

    tid = get_tenant_id()
    db = get_db()

    current = await db.query_one(
        "SELECT status FROM orders.leads WHERE id = $1 AND tenant_id = $2",
        [lead_id, tid],
        tenant_id=tid,
    )
    if current is None:
        return {"error": f"Lead '{lead_id}' not found for tenant '{tid}'"}

    current_status = current["status"]
    allowed = ALLOWED_TRANSITIONS.get(current_status, ())
    if status not in allowed:
        if not allowed:
            return {
                "error": (
                    f"Lead is in terminal status '{current_status}' - no further transitions allowed."
                )
            }
        return {
            "error": (
                f"Invalid transition '{current_status}' → '{status}'. "
                f"Allowed: {allowed}"
            )
        }

    sold_at = datetime.now(tz=timezone.utc) if status == "sold" else None

    row = await db.query_one(
        """
        UPDATE orders.leads
        SET status   = $3,
            sold_at  = COALESCE($4, sold_at)
        WHERE id = $1 AND tenant_id = $2
        RETURNING id, tenant_id, product, price, status, commission_amount,
                  created_at, sold_at
        """,
        [lead_id, tid, status, sold_at],
        tenant_id=tid,
    )

    logger.info("Updated lead id=%s %s→%s tenant=%s", lead_id, current_status, status, tid)
    return _lead_to_dict(row)


@mcp.tool()
async def get_leads(
    status: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List leads for the current tenant.

    Args:
        status: Filter by status ('new', 'qualified', 'sold', 'lost').
                If omitted, returns all leads.
        limit:  Maximum number of results (1–100). Defaults to 20.

    Returns:
        List of lead dicts ordered by created_at descending.
    """
    if status is not None and status not in VALID_STATUSES:
        return [{"error": f"Invalid status '{status}'. Valid: {VALID_STATUSES}"}]
    limit = min(max(limit, 1), 100)

    tid = get_tenant_id()
    db = get_db()

    if status:
        rows = await db.query(
            """
            SELECT id, tenant_id, product, price, status, commission_amount,
                   customer_tg_id, created_at, sold_at
            FROM orders.leads
            WHERE tenant_id = $1 AND status = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            [tid, status, limit],
            tenant_id=tid,
        )
    else:
        rows = await db.query(
            """
            SELECT id, tenant_id, product, price, status, commission_amount,
                   customer_tg_id, created_at, sold_at
            FROM orders.leads
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            [tid, limit],
            tenant_id=tid,
        )

    return [_lead_to_dict(r) for r in rows]


@mcp.tool()
async def get_lead_stats() -> dict:
    """Return aggregate lead statistics for the current tenant.

    Returns:
        total:              Total lead count.
        by_status:          Dict mapping status → count.
        total_commission:   Sum of commission_amount for 'sold' leads.
        total_revenue:      Sum of price for 'sold' leads.
    """
    tid = get_tenant_id()
    db = get_db()

    rows = await db.query(
        """
        SELECT status,
               COUNT(*)                           AS cnt,
               COALESCE(SUM(price), 0)            AS revenue,
               COALESCE(SUM(commission_amount), 0) AS commission
        FROM orders.leads
        WHERE tenant_id = $1
        GROUP BY status
        """,
        [tid],
        tenant_id=tid,
    )

    by_status: dict[str, int] = {}
    total_revenue = 0.0
    total_commission = 0.0

    for r in rows:
        by_status[r["status"]] = int(r["cnt"])
        if r["status"] == "sold":
            total_revenue = float(r["revenue"])
            total_commission = float(r["commission"])

    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
    }



def _lead_to_dict(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "tenant_id": row["tenant_id"],
        "product": row["product"],
        "price": float(row["price"]) if row["price"] is not None else None,
        "status": row["status"],
        "commission_amount": (
            float(row["commission_amount"]) if row["commission_amount"] is not None else None
        ),
        "customer_tg_id": row.get("customer_tg_id"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "sold_at": row["sold_at"].isoformat() if row.get("sold_at") else None,
    }



def main() -> None:
    import uvicorn

    app = mcp.http_app(path="/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
