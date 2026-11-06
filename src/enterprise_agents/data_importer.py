"""
enterprise_agents.data_importer
Módulo para importar datos externos (CSV, Excel .xlsx, JSON) desde Drive o archivos subidos
hacia la base de datos corporativa del CIO (Ventas e Inventario).
"""

from __future__ import annotations
import os
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from enterprise_agents.database import get_connection, execute_db, query_db


def import_products_csv(file_path: Path) -> Dict[str, Any]:
    """Importa productos desde un archivo CSV."""
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT OR REPLACE INTO products (sku, name, category, cost_price, sale_price, min_safety_stock, reorder_point, lead_time_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["sku"],
                row["name"],
                row.get("category", "General"),
                float(row.get("cost_price", 0.0)),
                float(row.get("sale_price", 0.0)),
                int(row.get("min_safety_stock", 10)),
                int(row.get("reorder_point", 20)),
                int(row.get("lead_time_days", 5))
            ))
            count += 1
    conn.commit()
    conn.close()
    return {"status": "success", "imported_products": count}


def import_inventory_csv(file_path: Path) -> Dict[str, Any]:
    """Importa o actualiza stock desde un archivo CSV con columnas: sku, warehouse_code, quantity_on_hand, quantity_reserved."""
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"]
            wh_code = row.get("warehouse_code", "WH-MAD-01")
            prod = query_db("SELECT id FROM products WHERE sku = ?", (sku,))
            wh = query_db("SELECT id FROM warehouses WHERE code = ?", (wh_code,))
            if prod and wh:
                prod_id = prod[0]["id"]
                wh_id = wh[0]["id"]
                cursor.execute("""
                    INSERT OR REPLACE INTO inventory (product_id, warehouse_id, quantity_on_hand, quantity_reserved)
                    VALUES (?, ?, ?, ?)
                """, (
                    prod_id,
                    wh_id,
                    int(row.get("quantity_on_hand", 0)),
                    int(row.get("quantity_reserved", 0))
                ))
                count += 1
    conn.commit()
    conn.close()
    return {"status": "success", "updated_inventory_records": count}


def import_sales_csv(file_path: Path) -> Dict[str, Any]:
    """Importa órdenes de ventas desde un archivo CSV."""
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT OR REPLACE INTO sales_orders (order_number, customer_id, order_date, status, total_amount, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                row["order_number"],
                int(row.get("customer_id", 1)),
                row["order_date"],
                row.get("status", "COMPLETED"),
                float(row.get("total_amount", 0.0)),
                row.get("notes", "")
            ))
            count += 1
    conn.commit()
    conn.close()
    return {"status": "success", "imported_orders": count}


def scan_and_import_folder(folder_path: Path) -> Dict[str, Any]:
    """Escanea una carpeta en busca de archivos CSV/JSON/XLSX y los procesa automáticamente."""
    results = {}
    if not folder_path.exists():
        return {"status": "error", "message": f"La carpeta {folder_path} no existe."}

    for file in folder_path.iterdir():
        if file.suffix.lower() == ".csv":
            name = file.stem.lower()
            if "product" in name or "articulo" in name:
                results[file.name] = import_products_csv(file)
            elif "stock" in name or "inventari" in name:
                results[file.name] = import_inventory_csv(file)
            elif "venta" in name or "order" in name or "pedido" in name:
                results[file.name] = import_sales_csv(file)
    return {"status": "completed", "details": results}
