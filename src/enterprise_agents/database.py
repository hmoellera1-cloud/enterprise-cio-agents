"""
enterprise_agents.database
Módulo de base de datos SQLite corporativa con esquemas y datos iniciales (seed)
para el sistema de agentes del CIO, Ventas e Inventario.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import datetime

import os

DEFAULT_DB_PATH = Path(os.environ.get("ENTERPRISE_DB_PATH", "/home/antigravity/enterprise_agents/enterprise.db"))


def set_default_db_path(path: Path) -> None:
    global DEFAULT_DB_PATH
    DEFAULT_DB_PATH = path


def _raw_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn



def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    must_init = not path.exists() or path.stat().st_size == 0
    conn = _raw_connection(path)
    if must_init:
        init_database(path, seed_data=True)
    return conn


def init_database(db_path: Optional[Path] = None, seed_data: bool = True) -> None:
    """Inicializa el esquema de la base de datos corporativa y carga datos de prueba."""
    path = db_path or DEFAULT_DB_PATH
    conn = _raw_connection(path)

    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        cost_price REAL NOT NULL,
        sale_price REAL NOT NULL,
        min_safety_stock INTEGER NOT NULL DEFAULT 10,
        reorder_point INTEGER NOT NULL DEFAULT 20,
        lead_time_days INTEGER NOT NULL DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL DEFAULT 10000
    );

    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
        quantity_on_hand INTEGER NOT NULL DEFAULT 0,
        quantity_reserved INTEGER NOT NULL DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, warehouse_id)
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        contact_email TEXT NOT NULL,
        segment TEXT NOT NULL,
        region TEXT NOT NULL,
        credit_limit REAL NOT NULL DEFAULT 50000.0
    );

    CREATE TABLE IF NOT EXISTS sales_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        order_date DATE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('COMPLETED', 'PENDING', 'PROCESSING', 'CANCELLED')),
        total_amount REAL NOT NULL DEFAULT 0.0,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES sales_orders(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        subtotal REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS restock_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_number TEXT UNIQUE NOT NULL,
        product_id INTEGER NOT NULL REFERENCES products(id),
        warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
        quantity INTEGER NOT NULL,
        urgency TEXT CHECK(urgency IN ('LOW', 'MEDIUM', 'HIGH', 'WARNING', 'CRITICAL')),
        status TEXT DEFAULT 'REQUESTED',
        reason TEXT,
        requested_by TEXT DEFAULT 'InventoryAgent',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    """)

    conn.commit()

    if seed_data:
        # Check if products table has rows
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            _seed_enterprise_data(cursor)
            conn.commit()

    conn.close()


def _seed_enterprise_data(cursor: sqlite3.Cursor) -> None:
    # 1. Almacenes
    warehouses = [
        ("WH-MAD-01", "Hub Logístico Central Madrid", "Madrid, España", 25000),
        ("WH-BCN-02", "Centro de Distribución Norte", "Barcelona, España", 15000),
        ("WH-VAL-03", "Almacén Logístico Mediterráneo", "Valencia, España", 10000),
    ]
    cursor.executemany(
        "INSERT INTO warehouses (code, name, location, capacity) VALUES (?, ?, ?, ?)",
        warehouses,
    )

    # 2. Productos corporativos tecnológicos
    products = [
        ("SKU-LAP-PRO16", "Laptop Pro Enterprise 16 inch i9/32GB", "Hardware", 1150.0, 1899.0, 15, 30, 7),
        ("SKU-LAP-AIR14", "Laptop Ultra Slim 14 inch M3/16GB", "Hardware", 850.0, 1399.0, 20, 40, 5),
        ("SKU-SRV-RACK2U", "Servidor Rack 2U Dual Xeon 64GB", "Infraestructura", 3200.0, 5200.0, 5, 10, 14),
        ("SKU-MON-4K32", "Monitor Curvo 4K 32 inch HDR", "Periféricos", 310.0, 580.0, 25, 50, 4),
        ("SKU-KEY-MEC01", "Teclado Mecánico Inalámbrico RGB", "Periféricos", 45.0, 95.0, 40, 80, 3),
        ("SKU-SWT-GIGA48", "Switch Gestionable 48 Puertos PoE+", "Redes", 620.0, 1050.0, 10, 20, 10),
        ("SKU-WAP-WIFI6E", "Punto de Acceso Empresarial WiFi 6E", "Redes", 180.0, 320.0, 30, 60, 5),
        ("SKU-DOCK-TB4", "Docking Station Thunderbolt 4 Dual 4K", "Accesorios", 120.0, 240.0, 25, 45, 6),
        ("SKU-UPS-SMART3K", "Sistema SAI/UPS Smart 3000VA On-Line", "Infraestructura", 950.0, 1600.0, 8, 15, 12),
        ("SKU-SEC-FIREWALL", "Appliance Firewall UTM 10Gbps NextGen", "Seguridad", 2100.0, 3600.0, 6, 12, 10),
    ]
    cursor.executemany(
        """INSERT INTO products (sku, name, category, cost_price, sale_price, 
           min_safety_stock, reorder_point, lead_time_days) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        products,
    )

    # 3. Niveles de inventario
    # Algunos con stock saludable, otros en nivel crítico/alerta para que los agentes lo detecten
    stock_distribution = [
        # prod_id, wh_id, qty_hand, qty_reserved
        (1, 1, 18, 5),    # SKU-LAP-PRO16: Total 28 (cerca de reorder_point 30)
        (1, 2, 10, 2),
        (2, 1, 8, 4),     # SKU-LAP-AIR14: Total 12 -> ¡ALERTA CRÍTICA! Min 20, reorder 40
        (2, 2, 4, 1),
        (3, 1, 6, 1),     # SKU-SRV-RACK2U: Total 9 (alerta reorder_point 10)
        (3, 3, 3, 0),
        (4, 1, 65, 10),   # SKU-MON-4K32: Total 95 (Saludable)
        (4, 2, 30, 5),
        (5, 1, 120, 15),  # SKU-KEY-MEC01: Total 185 (Excelente stock)
        (5, 2, 65, 5),
        (6, 1, 12, 4),    # SKU-SWT-GIGA48: Total 15 (Alerta < 20)
        (6, 3, 3, 0),
        (7, 1, 80, 12),   # SKU-WAP-WIFI6E: Total 120 (Saludable)
        (7, 2, 40, 8),
        (8, 1, 14, 6),    # SKU-DOCK-TB4: Total 22 -> ¡Bajo stock! (reorder 45, min 25)
        (8, 3, 8, 2),
        (9, 1, 9, 2),     # SKU-UPS-SMART3K: Total 14 (reorder 15)
        (9, 2, 5, 1),
        (10, 1, 4, 2),    # SKU-SEC-FIREWALL: Total 7 -> Alerta (< 12)
        (10, 2, 3, 1),
    ]
    cursor.executemany(
        """INSERT INTO inventory (product_id, warehouse_id, quantity_on_hand, quantity_reserved)
           VALUES (?, ?, ?, ?)""",
        stock_distribution,
    )

    # 4. Clientes corporativos
    customers = [
        ("Banco Santander Tech", "compras.ti@santander-tech.es", "Enterprise Financiero", "Madrid", 250000.0),
        ("Telefónica Soluciones Digitales", "procurement@telefonica-sol.es", "Telecomunicaciones", "Madrid", 300000.0),
        ("Inditex Sistemas Retail", "it.logistica@inditex-group.es", "Retail & Logística", "Galicia/Norte", 180000.0),
        ("Hospital Vall d'Hebron TI", "sistemas@vhebron-salud.cat", "Salud Pública", "Barcelona", 90000.0),
        ("Mercadona Cloud Hub", "infraestructura@mercadona-tech.es", "Retail & Distribución", "Valencia", 150000.0),
        ("SEAT Software Innovations", "digital.office@seat-code.es", "Automoción / Industrial", "Barcelona", 120000.0),
        ("BBVA Next Technologies", "cloud.enablement@bbva-next.es", "Fintech", "Madrid", 200000.0),
    ]
    cursor.executemany(
        """INSERT INTO customers (company_name, contact_email, segment, region, credit_limit)
           VALUES (?, ?, ?, ?, ?)""",
        customers,
    )

    # 5. Pedidos de venta históricos y recientes
    orders = [
        ("ORD-2026-001", 1, "2026-10-15", "COMPLETED", 34182.0, "Renovación parque de ingenieros"),
        ("ORD-2026-002", 2, "2026-10-20", "COMPLETED", 57200.0, "Despliegue Datacenter Nodo BCN"),
        ("ORD-2026-003", 3, "2026-10-28", "COMPLETED", 21750.0, "Equipamiento centros logísticos"),
        ("ORD-2026-004", 4, "2026-11-01", "COMPLETED", 15400.0, "Actualización puestos médicos"),
        ("ORD-2026-005", 5, "2026-11-03", "PROCESSING", 43280.0, "Expansión oficinas centrales"),
        ("ORD-2026-006", 6, "2026-11-04", "PROCESSING", 18990.0, "Lote 10 Laptops Pro Developer"),
        ("ORD-2026-007", 7, "2026-11-05", "PENDING", 28800.0, "Firewalls y Switches de Seguridad"),
    ]
    cursor.executemany(
        """INSERT INTO sales_orders (order_number, customer_id, order_date, status, total_amount, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        orders,
    )

    # Líneas de pedido
    order_items = [
        # ORD-2026-001: 18 laptops pro
        (1, 1, 18, 1899.0, 34182.0),
        # ORD-2026-002: 11 servidores
        (2, 3, 11, 5200.0, 57200.0),
        # ORD-2026-003: 15 monitors, 50 docks, 80 keyboards
        (3, 4, 15, 580.0, 8700.0),
        (3, 8, 35, 240.0, 8400.0),
        (3, 5, 48, 95.0, 4560.0),
        # ORD-2026-004: 11 laptops ultra slim
        (4, 2, 11, 1399.0, 15389.0),
        # ORD-2026-005: 12 laptops pro + 20 monitores + 20 docks
        (5, 1, 12, 1899.0, 22788.0),
        (5, 4, 20, 580.0, 11600.0),
        (5, 8, 37, 240.0, 8880.0),
        # ORD-2026-006: 10 laptops pro
        (6, 1, 10, 1899.0, 18990.0),
        # ORD-2026-007: 8 firewalls
        (7, 10, 8, 3600.0, 28800.0),
    ]
    cursor.executemany(
        """INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
           VALUES (?, ?, ?, ?, ?)""",
        order_items,
    )


def query_db(query: str, params: tuple = (), db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Ejecuta una consulta SQL SELECT y retorna una lista de diccionarios."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


def execute_db(query: str, params: tuple = (), db_path: Optional[Path] = None) -> int:
    """Ejecuta una sentencia SQL modificadora y retorna el id insertado o filas afectadas."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id
