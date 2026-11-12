"""
enterprise_agents.tools.inventory_tools
Herramientas analíticas y de control de existencias para el Agente de Inventarios.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import datetime
from enterprise_agents.database import query_db, execute_db


def get_inventory_kpis() -> Dict[str, Any]:
    """Calcula las métricas principales de almacenes y valoración de inventario."""
    stock_stats = query_db("""
        SELECT 
            COUNT(DISTINCT p.id) as total_products,
            COALESCE(SUM(inv.quantity_on_hand), 0) as total_units_on_hand,
            COALESCE(SUM(inv.quantity_reserved), 0) as total_units_reserved,
            COALESCE(SUM(inv.quantity_on_hand * p.cost_price), 0.0) as total_valuation_cost,
            COALESCE(SUM(inv.quantity_on_hand * p.sale_price), 0.0) as total_valuation_retail
        FROM products p
        LEFT JOIN inventory inv ON p.id = inv.product_id
    """)[0]

    warehouses = query_db("""
        SELECT 
            w.code,
            w.name,
            w.location,
            w.capacity,
            COALESCE(SUM(inv.quantity_on_hand), 0) as current_occupancy_units,
            ROUND((CAST(COALESCE(SUM(inv.quantity_on_hand), 0) AS REAL) / w.capacity) * 100, 2) as occupancy_rate_pct
        FROM warehouses w
        LEFT JOIN inventory inv ON w.id = inv.warehouse_id
        GROUP BY w.id
    """)

    return {
        "total_skus": stock_stats["total_products"],
        "total_units_on_hand": stock_stats["total_units_on_hand"],
        "total_units_reserved": stock_stats["total_units_reserved"],
        "total_units_available": stock_stats["total_units_on_hand"] - stock_stats["total_units_reserved"],
        "total_valuation_cost": round(stock_stats["total_valuation_cost"], 2),
        "total_valuation_retail": round(stock_stats["total_valuation_retail"], 2),
        "warehouses": [dict(w) for w in warehouses]
    }


def get_critical_stock_alerts() -> List[Dict[str, Any]]:
    """Identifica productos que se encuentran por debajo del stock de seguridad o punto de reorden."""
    query = """
        SELECT 
            p.id as product_id,
            p.sku,
            p.name,
            p.category,
            p.min_safety_stock,
            p.reorder_point,
            p.lead_time_days,
            COALESCE(SUM(inv.quantity_on_hand), 0) as total_on_hand,
            COALESCE(SUM(inv.quantity_reserved), 0) as total_reserved
        FROM products p
        LEFT JOIN inventory inv ON p.id = inv.product_id
        GROUP BY p.id
    """
    rows = query_db(query)
    alerts = []
    for r in rows:
        available = r["total_on_hand"] - r["total_reserved"]
        if available <= r["min_safety_stock"]:
            alerts.append({
                "sku": r["sku"],
                "name": r["name"],
                "category": r["category"],
                "total_on_hand": r["total_on_hand"],
                "total_reserved": r["total_reserved"],
                "available_stock": available,
                "min_safety_stock": r["min_safety_stock"],
                "reorder_point": r["reorder_point"],
                "lead_time_days": r["lead_time_days"],
                "urgency": "CRITICAL",
                "recommended_restock_qty": max(r["reorder_point"] * 2 - available, 20),
                "message": f"Stock disponible ({available}) está por debajo del stock de seguridad mínimo ({r['min_safety_stock']})."
            })
        elif available <= r["reorder_point"]:
            alerts.append({
                "sku": r["sku"],
                "name": r["name"],
                "category": r["category"],
                "total_on_hand": r["total_on_hand"],
                "total_reserved": r["total_reserved"],
                "available_stock": available,
                "min_safety_stock": r["min_safety_stock"],
                "reorder_point": r["reorder_point"],
                "lead_time_days": r["lead_time_days"],
                "urgency": "WARNING",
                "recommended_restock_qty": max(r["reorder_point"] * 2 - available, 10),
                "message": f"Stock disponible ({available}) alcanzó el punto de reorden ({r['reorder_point']})."
            })
    return alerts


def get_stock_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Consulta la distribución de existencias de un SKU en cada uno de los almacenes."""
    product = query_db("SELECT * FROM products WHERE sku = ?", (sku,))
    if not product:
        return None
    p = product[0]

    wh_distribution = query_db("""
        SELECT 
            w.code as warehouse_code,
            w.name as warehouse_name,
            inv.quantity_on_hand,
            inv.quantity_reserved,
            (inv.quantity_on_hand - inv.quantity_reserved) as quantity_available,
            inv.last_updated
        FROM inventory inv
        JOIN warehouses w ON inv.warehouse_id = w.id
        WHERE inv.product_id = ?
    """, (p["id"],))

    total_hand = sum(d["quantity_on_hand"] for d in wh_distribution)
    total_res = sum(d["quantity_reserved"] for d in wh_distribution)
    total_avail = total_hand - total_res

    return {
        "sku": p["sku"],
        "name": p["name"],
        "category": p["category"],
        "cost_price": p["cost_price"],
        "sale_price": p["sale_price"],
        "min_safety_stock": p["min_safety_stock"],
        "reorder_point": p["reorder_point"],
        "lead_time_days": p["lead_time_days"],
        "total_on_hand": total_hand,
        "total_reserved": total_res,
        "total_available": total_avail,
        "warehouses": [dict(d) for d in wh_distribution]
    }


def create_restock_request(sku: str, quantity: int, urgency: str = "MEDIUM", reason: str = "") -> Dict[str, Any]:
    """Crea una solicitud formal de reabastecimiento en la base de datos."""
    urgency_norm = urgency.upper() if urgency else "MEDIUM"
    if urgency_norm not in ["LOW", "MEDIUM", "HIGH", "WARNING", "CRITICAL"]:
        urgency_norm = "MEDIUM"

    product = query_db("SELECT id, name FROM products WHERE sku = ?", (sku,))
    if not product:
        return {"status": "error", "message": f"SKU {sku} no existe."}
    
    import uuid
    prod_id = product[0]["id"]
    warehouse_id = 1
    req_number = f"REQ-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}-{uuid.uuid4().hex[:4].upper()}"

    req_id = execute_db("""

        INSERT INTO restock_requests (request_number, product_id, warehouse_id, quantity, urgency, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (req_number, prod_id, warehouse_id, quantity, urgency_norm, reason))


    return {
        "status": "success",
        "request_id": req_id,
        "request_number": req_number,
        "product": product[0]["name"],
        "quantity": quantity,
        "urgency": urgency,
        "warehouse": "Hub Logístico Central Madrid"
    }


def check_stock_availability(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verifica si hay stock suficiente para una lista de productos pedidos."""
    results = []
    all_sufficient = True

    for it in items:
        sku = it.get("sku")
        needed_qty = it.get("quantity", 0)
        stock_info = get_stock_by_sku(sku)
        if not stock_info:
            all_sufficient = False
            results.append({
                "sku": sku,
                "needed": needed_qty,
                "available": 0,
                "sufficient": False,
                "error": "SKU no encontrado"
            })
            continue

        available = stock_info["total_available"]
        sufficient = available >= needed_qty
        if not sufficient:
            all_sufficient = False

        results.append({
            "sku": sku,
            "product_name": stock_info["name"],
            "needed": needed_qty,
            "available": available,
            "sufficient": sufficient,
            "deficit": max(0, needed_qty - available)
        })

    return {
        "all_items_sufficient": all_sufficient,
        "items": results
    }


def search_inventory_by_keyword(keyword: str) -> Dict[str, Any]:
    """Busca existencias en inventario por nombre de producto o código SKU (con normalización de plurales)."""
    clean_kw = keyword.lower().strip()
    words = [w for w in clean_kw.split() if len(w) > 1]
    norm_words = [w[:-1] if w.endswith('s') and len(w) > 3 else w for w in words]
    if not norm_words:
        norm_words = [clean_kw]

    conds = " AND ".join(["(LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ?)" for _ in norm_words])
    params = []
    for w in norm_words:
        params.extend([f"%{w}%", f"%{w}%"])

    rows = query_db(f"""
        SELECT 
            p.sku,
            p.name,
            p.cost_price,
            p.sale_price,
            COALESCE(SUM(i.quantity_on_hand), 0) as on_hand,
            COALESCE(SUM(i.quantity_reserved), 0) as reserved,
            COALESCE(SUM(i.quantity_on_hand - i.quantity_reserved), 0) as available
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE {conds}
        GROUP BY p.id
        ORDER BY on_hand DESC, p.name ASC
        LIMIT 25
    """, tuple(params))

    total_on_hand = sum(int(r["on_hand"]) for r in rows)
    total_reserved = sum(int(r["reserved"]) for r in rows)
    total_available = sum(int(r["available"]) for r in rows)
    total_cost_val = sum((r["on_hand"] or 0) * (r["cost_price"] or 0) for r in rows)

    wh_rows = query_db(f"""
        SELECT 
            w.code,
            w.name as warehouse_name,
            COALESCE(SUM(i.quantity_on_hand), 0) as on_hand,
            COALESCE(SUM(i.quantity_on_hand - i.quantity_reserved), 0) as available
        FROM products p
        JOIN inventory i ON p.id = i.product_id
        JOIN warehouses w ON i.warehouse_id = w.id
        WHERE {conds}
        GROUP BY w.id
        HAVING on_hand > 0
        ORDER BY available DESC
    """, tuple(params))

    return {
        "keyword": keyword,
        "total_variants": len(rows),
        "total_on_hand": total_on_hand,
        "total_reserved": total_reserved,
        "total_available": total_available,
        "total_cost_valuation": round(total_cost_val, 2),
        "warehouses": [
            {
                "code": w["code"],
                "name": w["warehouse_name"],
                "on_hand": int(w["on_hand"]),
                "available": int(w["available"])
            }
            for w in wh_rows
        ],
        "variants": [
            {
                "sku": r["sku"],
                "name": r["name"],
                "units_sold": int(r["available"]),
                "revenue": round((r["available"] or 0) * (r["sale_price"] or 0), 2),
                "on_hand": int(r["on_hand"]),
                "reserved": int(r["reserved"]),
                "available": int(r["available"]),
                "cost_price": round(r["cost_price"] or 0, 2),
                "sale_price": round(r["sale_price"] or 0, 2)
            }
            for r in rows
        ]
    }


def get_warehouses_summary(limit: int = 15) -> Dict[str, Any]:
    """Obtiene el listado de bodegas/almacenes con su inventario físico y valoración."""
    rows = query_db("""
        SELECT 
            w.code,
            w.name,
            w.location,
            COUNT(DISTINCT i.product_id) as skus_count,
            COALESCE(SUM(i.quantity_on_hand), 0) as on_hand,
            COALESCE(SUM(i.quantity_on_hand - i.quantity_reserved), 0) as available,
            COALESCE(SUM(i.quantity_on_hand * p.cost_price), 0) as cost_val
        FROM warehouses w
        LEFT JOIN inventory i ON w.id = i.warehouse_id
        LEFT JOIN products p ON i.product_id = p.id
        GROUP BY w.id
        ORDER BY on_hand DESC
        LIMIT ?
    """, (limit,))
    total_wh = query_db("SELECT COUNT(*) as c FROM warehouses")[0]["c"]
    return {
        "total_warehouses": total_wh,
        "warehouses": [
            {
                "sku": r["code"],
                "name": r["name"],
                "units_sold": int(r["on_hand"]),
                "revenue": round(r["cost_val"], 2),
                "skus_count": int(r["skus_count"]),
                "available": int(r["available"])
            }
            for r in rows
        ]
    }


def get_out_of_stock_products(limit: int = 15) -> List[Dict[str, Any]]:
    """Lista los productos sin stock disponible (dando prioridad a los que tienen historial de ventas)."""
    rows = query_db("""
        SELECT 
            p.sku,
            p.name,
            p.sale_price,
            COALESCE(SUM(i.quantity_on_hand), 0) as on_hand,
            COALESCE(SUM(i.quantity_reserved), 0) as reserved,
            COALESCE((SELECT SUM(oi.quantity) FROM order_items oi WHERE oi.product_id = p.id), 0) as sold_qty
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        GROUP BY p.id
        HAVING (on_hand - reserved) <= 0
        ORDER BY sold_qty DESC, p.name ASC
        LIMIT ?
    """, (limit,))
    return [
        {
            "sku": r["sku"],
            "name": r["name"],
            "units_sold": int(r["sold_qty"]),
            "revenue": round((r["sold_qty"] or 0) * (r["sale_price"] or 0), 2),
        }
        for r in rows
    ]

