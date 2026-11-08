"""
enterprise_agents.tools.sales_tools
Herramientas analíticas y transaccionales para el Agente de Ventas.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from enterprise_agents.database import query_db, execute_db


def get_sales_kpis() -> Dict[str, Any]:
    """Calcula los KPIs generales de ventas de la empresa."""
    totals = query_db("""
        SELECT 
            COUNT(id) as total_orders,
            COALESCE(SUM(total_amount), 0.0) as total_revenue,
            COALESCE(AVG(total_amount), 0.0) as avg_order_value,
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_orders,
            SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as processing_orders
        FROM sales_orders
    """)[0]

    return {
        "total_revenue": round(totals["total_revenue"], 2),
        "total_orders": totals["total_orders"],
        "completed_orders": totals["completed_orders"] or 0,
        "pending_orders": totals["pending_orders"] or 0,
        "processing_orders": totals["processing_orders"] or 0,
        "average_order_value": round(totals["avg_order_value"], 2),
    }


def get_top_selling_products(limit: int = 5) -> List[Dict[str, Any]]:
    """Obtiene los productos con mayor volumen y facturación en ventas."""
    query = """
        SELECT 
            p.sku,
            p.name,
            p.category,
            SUM(oi.quantity) as total_units_sold,
            SUM(oi.subtotal) as total_revenue,
            COALESCE(SUM(inv.quantity_on_hand), 0) as current_stock_on_hand,
            COALESCE(SUM(inv.quantity_reserved), 0) as current_stock_reserved
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN inventory inv ON p.id = inv.product_id
        GROUP BY p.id
        ORDER BY total_revenue DESC
        LIMIT ?
    """
    rows = query_db(query, (limit,))
    result = []
    for r in rows:
        available = (r["current_stock_on_hand"] or 0) - (r["current_stock_reserved"] or 0)
        status = "HEALTHY" if available > 15 else ("WARNING" if available > 5 else "CRITICAL")
        result.append({
            "sku": r["sku"],
            "name": r["name"],
            "category": r["category"],
            "units_sold": r["total_units_sold"],
            "revenue": round(r["total_revenue"], 2),
            "stock_on_hand": r["current_stock_on_hand"],
            "stock_available": available,
            "stock_status": status
        })
    return result


def get_sales_by_region() -> Dict[str, float]:
    """Obtiene la distribución de ingresos por región geográfica de clientes."""
    rows = query_db("""
        SELECT c.region, COALESCE(SUM(so.total_amount), 0.0) as revenue
        FROM customers c
        JOIN sales_orders so ON c.id = so.customer_id
        GROUP BY c.region
        ORDER BY revenue DESC
    """)
    return {r["region"]: round(r["revenue"], 2) for r in rows}


def get_sales_by_category() -> Dict[str, float]:
    """Obtiene los ingresos desglosados por categoría de producto."""
    rows = query_db("""
        SELECT p.category, COALESCE(SUM(oi.subtotal), 0.0) as revenue
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        GROUP BY p.category
        ORDER BY revenue DESC
    """)
    return {r["category"]: round(r["revenue"], 2) for r in rows}


def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
    """Obtiene los pedidos más recientes con detalle de cliente y estado."""
    rows = query_db("""
        SELECT 
            so.order_number,
            c.company_name as customer,
            c.region,
            so.order_date,
            so.status,
            so.total_amount,
            so.notes
        FROM sales_orders so
        JOIN customers c ON so.customer_id = c.id
        ORDER BY so.order_date DESC, so.id DESC
        LIMIT ?
    """, (limit,))
    return [dict(r) for r in rows]


def get_sales_pipeline_insights() -> Dict[str, Any]:
    """Proporciona un diagnóstico de pedidos pendientes/en proceso y riesgo comercial."""
    kpis = get_sales_kpis()
    pending_revenue = query_db("""
        SELECT COALESCE(SUM(total_amount), 0.0) as pending_val
        FROM sales_orders 
        WHERE status IN ('PENDING', 'PROCESSING')
    """)[0]["pending_val"]

    return {
        "kpis": kpis,
        "committed_or_pending_revenue": round(pending_revenue, 2),
        "pipeline_health": "STRONG" if pending_revenue > 30000 else "NORMAL",
        "fulfillment_rate_pct": round((kpis["completed_orders"] / max(kpis["total_orders"], 1)) * 100, 1)
    }


def search_product_sales(keyword: str, month: Optional[str] = None) -> Dict[str, Any]:
    """Busca ventas acumuladas de un producto o categoría por palabra clave y opcionalmente por mes."""
    month_map = {
        "enero": "-01-", "febrero": "-02-", "marzo": "-03-", "abril": "-04-",
        "mayo": "-05-", "junio": "-06-", "julio": "-07-", "agosto": "-08-",
        "septiembre": "-09-", "octubre": "-10-", "noviembre": "-11-", "diciembre": "-12-"
    }

    date_filter = None
    if month:
        m_lower = month.lower().strip()
        date_filter = f"%{month_map.get(m_lower, f'-{m_lower.zfill(2)}-')}%"

    clean_kw = keyword.lower().strip()
    words = [w for w in clean_kw.split() if len(w) > 1]
    norm_words = [w[:-1] if w.endswith('s') and len(w) > 3 else w for w in words]
    if not norm_words:
        norm_words = [clean_kw]

    conds = " AND ".join(["(LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ?)" for _ in norm_words])
    params = []
    for w in norm_words:
        params.extend([f"%{w}%", f"%{w}%"])

    if date_filter:
        query = f"""
            SELECT 
                p.sku,
                p.name,
                SUM(oi.quantity) as total_qty,
                SUM(oi.subtotal) as total_revenue,
                AVG(oi.unit_price) as avg_price,
                COUNT(DISTINCT so.id) as orders_count
            FROM order_items oi
            JOIN sales_orders so ON oi.order_id = so.id
            JOIN products p ON oi.product_id = p.id
            WHERE {conds}
              AND so.order_date LIKE ?
            GROUP BY p.id
            ORDER BY total_qty DESC
        """
        params.append(date_filter)
        rows = query_db(query, tuple(params))
    else:
        query = f"""
            SELECT 
                p.sku,
                p.name,
                SUM(oi.quantity) as total_qty,
                SUM(oi.subtotal) as total_revenue,
                AVG(oi.unit_price) as avg_price,
                COUNT(DISTINCT so.id) as orders_count
            FROM order_items oi
            JOIN sales_orders so ON oi.order_id = so.id
            JOIN products p ON oi.product_id = p.id
            WHERE {conds}
            GROUP BY p.id
            ORDER BY total_qty DESC
        """
        rows = query_db(query, tuple(params))

    total_units = sum(r["total_qty"] for r in rows)
    total_revenue = sum(r["total_revenue"] for r in rows)

    return {
        "keyword": keyword,
        "month": month,
        "total_units_sold": int(total_units),
        "total_revenue": round(total_revenue, 2),
        "total_variants": len(rows),
        "variants": [
            {
                "sku": r["sku"],
                "name": r["name"],
                "units_sold": int(r["total_qty"]),
                "revenue": round(r["total_revenue"], 2),
                "avg_price": round(r["avg_price"], 2),
                "orders_count": r["orders_count"]
            }
            for r in rows
        ]
    }

