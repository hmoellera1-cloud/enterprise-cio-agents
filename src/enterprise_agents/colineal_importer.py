"""
enterprise_agents.colineal_importer
Importador especializado para los archivos ODBC extraídos de Colineal (ctin_produccion):
- odbc_productos.csv
- odbc_stock.csv
- odbc_ventas.csv
- odbc_reorden.csv
- facturado_sin_despacho.csv
"""

from __future__ import annotations
import csv
import sqlite3
from pathlib import Path
from typing import Dict, Any
from enterprise_agents.database import get_connection, set_default_db_path, DEFAULT_DB_PATH


def import_colineal_data(data_dir: Path) -> Dict[str, Any]:
    """Carga los datos reales de Colineal en la base de datos empresarial SQLite."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {
        "products": 0,
        "warehouses": 0,
        "stock_records": 0,
        "customers": 0,
        "orders": 0,
        "order_items": 0
    }

    # 1. Cargar Productos
    prod_file = data_dir / "odbc_productos.csv"
    product_map = {}  # codigo -> product_id

    if prod_file.exists():
        print("Importando productos...")
        with open(prod_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                sku = row.get("codigo", "").strip()
                if not sku:
                    continue
                name = row.get("nombre", "").strip() or sku
                category = row.get("categoria", "General").strip()
                try:
                    cost = float(row.get("costo", "0").replace(",", "."))
                except ValueError:
                    cost = 0.0
                sale_price = round(cost * 1.45, 2) if cost > 0 else 100.0

                cursor.execute("""
                    INSERT INTO products (sku, name, category, cost_price, sale_price, min_safety_stock, reorder_point, lead_time_days)
                    VALUES (?, ?, ?, ?, ?, 10, 25, 7)
                    ON CONFLICT(sku) DO UPDATE SET
                        name=excluded.name,
                        category=excluded.category,
                        cost_price=excluded.cost_price,
                        sale_price=excluded.sale_price
                """, (sku, name, category, cost, sale_price))
                stats["products"] += 1

        conn.commit()

        # Cachear product ids
        cursor.execute("SELECT sku, id FROM products")
        for row in cursor.fetchall():
            product_map[row[0]] = row[1]

    # 2. Cargar Stock y Almacenes
    stock_file = data_dir / "odbc_stock.csv"
    warehouse_map = {}  # nombre_almacen -> warehouse_id

    # Obtener almacenes existentes
    cursor.execute("SELECT name, id FROM warehouses")
    for row in cursor.fetchall():
        warehouse_map[row[0]] = row[1]

    if stock_file.exists():
        print("Importando existencias y almacenes...")
        with open(stock_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                sku = row.get("codigo", "").strip()
                wh_name = row.get("almacen", "").strip()
                if not sku or not wh_name:
                    continue

                # Si el almacén no existe, crearlo
                if wh_name not in warehouse_map:
                    wh_code = f"WH-{len(warehouse_map) + 1:03d}"
                    cursor.execute("""
                        INSERT INTO warehouses (code, name, location, capacity)
                        VALUES (?, ?, 'Planta / Centro Colineal', 50000)
                    """, (wh_code, wh_name))
                    warehouse_map[wh_name] = cursor.lastrowid
                    stats["warehouses"] += 1

                wh_id = warehouse_map[wh_name]
                prod_id = product_map.get(sku)
                if not prod_id:
                    # Crear producto dummy si no estaba en productos.csv
                    cursor.execute("""
                        INSERT OR IGNORE INTO products (sku, name, category, cost_price, sale_price, min_safety_stock, reorder_point)
                        VALUES (?, ?, 'Materia Prima / Insumo', 10.0, 15.0, 10, 25)
                    """, (sku, sku))
                    cursor.execute("SELECT id FROM products WHERE sku = ?", (sku,))
                    prod_id = cursor.fetchone()[0]
                    product_map[sku] = prod_id
                    stats["products"] += 1

                try:
                    qty_hand = float(row.get("cantidad", "0").replace(",", "."))
                    qty_res = float(row.get("reservado", "0").replace(",", "."))
                except ValueError:
                    qty_hand, qty_res = 0.0, 0.0

                cursor.execute("""
                    INSERT INTO inventory (product_id, warehouse_id, quantity_on_hand, quantity_reserved)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id, warehouse_id) DO UPDATE SET
                        quantity_on_hand=excluded.quantity_on_hand,
                        quantity_reserved=excluded.quantity_reserved
                """, (prod_id, wh_id, int(qty_hand), int(qty_res)))
                stats["stock_records"] += 1

        conn.commit()

    # 3. Cargar Ventas y Clientes
    ventas_file = data_dir / "odbc_ventas.csv"
    customer_map = {}  # nombre_cliente -> customer_id

    cursor.execute("SELECT company_name, id FROM customers")
    for row in cursor.fetchall():
        customer_map[row[0]] = row[1]

    if ventas_file.exists():
        print("Importando facturación y pedidos de ventas...")
        orders_dict = {}  # doc_number -> {customer_id, date, total, items: [(prod_id, qty, price, subtotal)]}

        with open(ventas_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                cliente = row.get("cliente", "").strip() or "Consumidor Final"
                doc = row.get("documento", "").strip()
                fecha = row.get("fecha", "").strip()
                sku = row.get("codigo", "").strip()
                if not doc or not fecha or not sku:
                    continue

                if cliente not in customer_map:
                    cursor.execute("""
                        INSERT INTO customers (company_name, contact_email, segment, region, credit_limit)
                        VALUES (?, 'contacto@cliente.com', 'Comercial / B2B', 'Ecuador', 100000.0)
                    """, (cliente,))
                    customer_map[cliente] = cursor.lastrowid
                    stats["customers"] += 1

                cust_id = customer_map[cliente]

                try:
                    cant = float(row.get("cantidad", "0").replace(",", "."))
                    subtotal = float(row.get("subtotal", "0").replace(",", "."))
                    unit_price = round(subtotal / max(cant, 1.0), 2)
                except ValueError:
                    cant, subtotal, unit_price = 1.0, 0.0, 0.0

                prod_id = product_map.get(sku)
                if not prod_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO products (sku, name, category, cost_price, sale_price, min_safety_stock, reorder_point)
                        VALUES (?, ?, 'Ventas / Producto', 50.0, 100.0, 10, 25)
                    """, (sku, row.get("producto", sku)))
                    cursor.execute("SELECT id FROM products WHERE sku = ?", (sku,))
                    prod_id = cursor.fetchone()[0]
                    product_map[sku] = prod_id
                    stats["products"] += 1

                if doc not in orders_dict:
                    orders_dict[doc] = {
                        "customer_id": cust_id,
                        "date": fecha,
                        "total": 0.0,
                        "items": []
                    }

                orders_dict[doc]["total"] += subtotal
                orders_dict[doc]["items"].append((prod_id, int(cant), unit_price, subtotal))

        # Insertar órdenes y sus líneas en lotes
        for doc_num, odata in orders_dict.items():
            cursor.execute("""
                INSERT INTO sales_orders (order_number, customer_id, order_date, status, total_amount, notes)
                VALUES (?, ?, ?, 'COMPLETED', ?, 'Documento Odoo/ODBC Colineal')
                ON CONFLICT(order_number) DO UPDATE SET total_amount=excluded.total_amount
            """, (doc_num, odata["customer_id"], odata["date"], round(odata["total"], 2)))
            order_id = cursor.lastrowid or 1
            stats["orders"] += 1

            for prod_id, qty, uprice, stotal in odata["items"]:
                cursor.execute("""
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, prod_id, qty, uprice, stotal))
                stats["order_items"] += 1

        conn.commit()

    conn.close()
    return stats


if __name__ == "__main__":
    from pathlib import Path
    data_path = Path("/home/antigravity/enterprise_agents/data")
    result = import_colineal_data(data_path)
    print("Resultado de la importación:", result)
