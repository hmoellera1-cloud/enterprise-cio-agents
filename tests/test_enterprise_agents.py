"""
Pruebas unitarias y de integración para el sistema multi-agente (CIO, Ventas, Inventario).
"""

import unittest
from pathlib import Path
import tempfile
from enterprise_agents.database import init_database, query_db, get_connection, set_default_db_path
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent
from enterprise_agents.agents.cio_orchestrator import CIOAgent


class TestEnterpriseMultiAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Usar base de datos temporal para pruebas
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db = Path(cls.temp_dir.name) / "test_enterprise.db"
        set_default_db_path(cls.test_db)
        init_database(cls.test_db, seed_data=True)


    @classmethod
    def tearDownClass(cls):
        set_default_db_path(Path("/home/antigravity/enterprise_agents/enterprise.db"))
        cls.temp_dir.cleanup()


    def test_database_seed_data(self):
        """Verifica que las tablas se hayan poblado con productos, almacenes, clientes y pedidos."""
        products = query_db("SELECT COUNT(*) as c FROM products", db_path=self.test_db)
        warehouses = query_db("SELECT COUNT(*) as c FROM warehouses", db_path=self.test_db)
        customers = query_db("SELECT COUNT(*) as c FROM customers", db_path=self.test_db)
        orders = query_db("SELECT COUNT(*) as c FROM sales_orders", db_path=self.test_db)

        self.assertGreaterEqual(products[0]["c"], 10)
        self.assertEqual(warehouses[0]["c"], 3)
        self.assertGreaterEqual(customers[0]["c"], 5)
        self.assertGreaterEqual(orders[0]["c"], 5)

    def test_sales_agent_kpis_and_top_products(self):
        """Prueba que el agente de ventas calcule KPIs e identifique top productos."""
        agent = SalesAgent()
        resp_kpi = agent.handle_request("resumen general kpis")
        self.assertEqual(resp_kpi.status, "success")
        self.assertIn("kpis", resp_kpi.details)
        self.assertGreater(resp_kpi.details["kpis"]["total_revenue"], 100000.0)

        resp_top = agent.handle_request("cuales son los top productos")
        self.assertEqual(resp_top.status, "success")
        self.assertIn("top_products", resp_top.details)
        self.assertTrue(len(resp_top.details["top_products"]) > 0)

    def test_inventory_agent_critical_alerts_and_restock(self):
        """Prueba la detección de inventario crítico y generación de orden de reposición."""
        agent = InventoryAgent()
        resp_alerts = agent.handle_request("mostrar alertas criticas de inventario")
        self.assertIn(resp_alerts.status, ["warning", "success"])
        self.assertIn("alerts", resp_alerts.details)
        self.assertGreater(len(resp_alerts.details["alerts"]), 0)

        # Probar solicitud de reorden
        resp_restock = agent.handle_request("crear solicitud de reabastecer inventario")
        self.assertEqual(resp_restock.status, "success")
        self.assertIn("restock_orders", resp_restock.details)

    def test_cio_executive_briefing_and_cross_functional_correlation(self):
        """Prueba que el CIO sintetice la visión cruzada de Ventas e Inventario."""
        cio = CIOAgent()
        briefing = cio.generate_executive_briefing()

        self.assertIsNotNone(briefing.title)
        self.assertIsNotNone(briefing.cio_perspective)
        self.assertGreater(briefing.sales_kpis["total_revenue"], 0)
        self.assertGreater(briefing.inventory_kpis["total_units_on_hand"], 0)
        self.assertGreater(len(briefing.cross_functional_alerts), 0)
        self.assertGreater(len(briefing.strategic_initiatives), 0)

    def test_cio_deal_simulation(self):
        """Prueba la simulación de viabilidad de venta por parte del CIO."""
        cio = CIOAgent()
        # Caso 1: pedido viable
        feasible_deal = [{"sku": "SKU-MON-4K32", "quantity": 5}]
        res1 = cio.simulate_deal_feasibility(feasible_deal, client_name="Cliente A")
        self.assertTrue(res1["is_feasible_immediately"])
        self.assertGreater(res1["total_deal_revenue"], 0)

        # Caso 2: pedido que excede el stock disponible
        unfeasible_deal = [{"sku": "SKU-LAP-AIR14", "quantity": 500}]
        res2 = cio.simulate_deal_feasibility(unfeasible_deal, client_name="Cliente B")
        self.assertFalse(res2["is_feasible_immediately"])


if __name__ == "__main__":
    unittest.main()
