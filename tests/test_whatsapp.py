import unittest
from pathlib import Path
from enterprise_agents.database import init_database, set_default_db_path
from enterprise_agents.whatsapp_service import process_whatsapp_message, generate_twiml_response


class TestWhatsAppIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_default_db_path(Path("/home/antigravity/enterprise_agents/enterprise.db"))
        init_database(Path("/home/antigravity/enterprise_agents/enterprise.db"), seed_data=True)

    def test_process_whatsapp_sales_query(self):
        msg = "¿Cuál es el resumen de ventas?"
        response = process_whatsapp_message(msg)
        self.assertIn("Director de Información (CIO - CTIN)", response)
        self.assertIn("Facturación Total", response)
        self.assertIn("Recomendaciones Estratégicas", response)

    def test_process_whatsapp_inventory_query(self):
        msg = "Alerta de stock crítico"
        response = process_whatsapp_message(msg)
        self.assertIn("Director de Información (CIO - CTIN)", response)
        self.assertTrue("Auditoría de Almacén" in response or "almacén" in response.lower())

    def test_process_whatsapp_product_search(self):
        msg = "¿Cuántas salas westin se vendieron en octubre?"
        response = process_whatsapp_message(msg)
        self.assertIn("Director de Información (CIO - CTIN)", response)
        self.assertIn("98 unidades", response)
        self.assertIn("USD", response)


    def test_generate_twiml_xml(self):
        body = "Hola CIO *negrita*"
        xml = generate_twiml_response(body)
        self.assertIn("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", xml)
        self.assertIn("<Response>", xml)
        self.assertIn("<Message>", xml)
        self.assertIn("Hola CIO *negrita*", xml)


if __name__ == "__main__":
    unittest.main()
