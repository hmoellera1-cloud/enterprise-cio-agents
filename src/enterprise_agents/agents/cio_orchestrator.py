"""
enterprise_agents.agents.cio_orchestrator
Director de Información (CIO) - Orquestador principal del ecosistema de datos empresariales.
Coordina a los agentes de Ventas e Inventario, cruza información y genera reportes ejecutivos.
"""

from __future__ import annotations
import datetime
from typing import Any, Dict, List, Optional
from enterprise_agents.agents.base_agent import BaseAgent
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent
from enterprise_agents.models import AgentResponse, ExecutiveBriefing, CrossAgentAlert


class CIOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CIO_DirectorDeInformacion",
            role="Chief Information Officer (CIO)",
            description="Director de Información de la empresa. Orquesta los flujos de datos estratégicos, coordina a los agentes de Ventas e Inventario, y genera reportes ejecutivos de alto impacto.",
            system_prompt="""
Eres el Director de Información (CIO) de la empresa.
Tu misión es integrar la visión estratégica corporativa con los datos operativos:
1. Coordinas al Agente de Ventas y al Agente de Inventarios.
2. Detectas discrepancias y riesgos cruzados (ej. productos top ventas con stock en quiebre inminente).
3. Emites directivas claras, optimizadas para el comité de dirección (CEO, CFO, COO).
4. Garantizas la coherencia, veracidad y oportunidad de los datos del negocio.
"""
        )
        # Subagentes especializados a su cargo
        self.sales_agent = SalesAgent()
        self.inventory_agent = InventoryAgent()

    def generate_executive_briefing(self) -> ExecutiveBriefing:
        """Consolida la información de Ventas e Inventario en un informe ejecutivo para la dirección."""
        # 1. Obtener métricas de Ventas
        sales_resp = self.sales_agent.handle_request("resumen general kpis")
        top_sales_resp = self.sales_agent.handle_request("top productos mas vendidos")
        
        # 2. Obtener métricas de Inventario
        inv_resp = self.inventory_agent.handle_request("resumen general valoracion")
        alerts_resp = self.inventory_agent.handle_request("alertas stock critico")

        sales_kpis = sales_resp.details.get("kpis", {})
        top_products = top_sales_resp.details.get("top_products", [])
        inv_kpis = inv_resp.details.get("kpis", {})
        inv_alerts = alerts_resp.details.get("alerts", [])

        # 3. Motor de cruce de datos (Cross-Functional Intelligence)
        cross_alerts: List[CrossAgentAlert] = []
        
        # Mapeo de SKUs con riesgo
        for top_prod in top_products:
            sku = top_prod["sku"]
            for alert in inv_alerts:
                if alert["sku"] == sku:
                    cross_alerts.append(CrossAgentAlert(
                        severity="CRITICAL" if alert["urgency"] == "CRITICAL" else "WARNING",
                        title=f"Riesgo de Desabasto en Producto Top: {top_prod['name']}",
                        description=f"El producto genera ${top_prod['revenue']:,} en facturación ({top_prod['units_sold']} uds vendidas) pero sólo tiene {alert['available_stock']} unidades disponibles frente a un mínimo de seguridad de {alert['min_safety_stock']}.",
                        sales_impact="Peligro de cancelación de pedidos pendientes e insatisfacción de clientes clave.",
                        inventory_impact=f"Requiere reorden inmediata de {alert['recommended_restock_qty']} unidades. Tiempo de reposición de proveedor: {alert['lead_time_days']} días.",
                        recommended_action=f"Aprobar orden de compra prioritaria para SKU {sku} y coordinar con Ventas para no comprometer entregas en los próximos {alert['lead_time_days']} días."
                    ))

        # Alertas de almacén generales para productos críticos (hasta 20 adicionales)
        for alert in inv_alerts:
            if len(cross_alerts) >= 25:
                break
            if not any(ca.title.find(alert["sku"]) != -1 for ca in cross_alerts) and alert["urgency"] == "CRITICAL":
                cross_alerts.append(CrossAgentAlert(
                    severity="WARNING",
                    title=f"Stock Crítico en {alert['name']} ({alert['sku']})",
                    description=alert["message"],
                    sales_impact="Sin impacto inmediato en el top 5, pero restringe futuras cotizaciones.",
                    inventory_impact=f"Stock físico actual: {alert['total_on_hand']} unidades.",
                    recommended_action=f"Reabastecer {alert['recommended_restock_qty']} unidades con urgencia {alert['urgency']}."
                ))

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cio_perspective = (
            "CTIN mantiene una sólida tracción comercial con $"
            f"{sales_kpis.get('total_revenue', 0):,} facturados. Sin embargo, la salud de la cadena de suministro "
            f"muestra {len(cross_alerts)} puntos de tensión crítica donde el volumen de demanda supera el stock de seguridad. "
            "Como CIO de CTIN, recomiendo sincronizar de inmediato las consultas ODBC/ERP con los centros de distribución y proveedores "
            "para automatizar el reordenamiento preventivo basado en demanda predictiva."
        )

        executive_summary = (
            f"Balance Corporativo CTIN: Ingresos de ${sales_kpis.get('total_revenue', 0):,} en {sales_kpis.get('total_orders', 0)} pedidos. "
            f"Valoración de existencias en almacenes: ${inv_kpis.get('total_valuation_cost', 0):,} (coste) y ${inv_kpis.get('total_valuation_retail', 0):,} (venta). "
            f"Unidades disponibles no comprometidas: {inv_kpis.get('total_units_available', 0)}. "
            f"Se identificaron {len(cross_alerts)} alertas operativas que requieren atención directiva."
        )

        initiatives = [
            "1. Conexión automatizada entre el módulo de Ventas y Almacenes de CTIN para reserva en tiempo real de inventario.",
            "2. Establecer acuerdo SLA con proveedores clave para reducir lead times de reposición.",
            "3. Habilitar tablero ejecutivo en tiempo real para visibilidad de directores (Ventas, Operaciones, Finanzas).",
            "4. Autorizar compra y órdenes de fabricación de reposición para los productos estrella con stock bajo."
        ]

        return ExecutiveBriefing(
            title="Informe Ejecutivo Integral del CIO - CTIN: Sincronización Ventas e Inventario",
            generated_at=now_str,
            executive_summary=executive_summary,
            cio_perspective=cio_perspective,

            sales_kpis=sales_kpis,
            inventory_kpis=inv_kpis,
            cross_functional_alerts=cross_alerts,
            strategic_initiatives=initiatives
        )

    def simulate_deal_feasibility(self, requested_items: List[Dict[str, Any]], client_name: str = "Cliente Corporativo") -> Dict[str, Any]:
        """El CIO evalúa la viabilidad operativa y de stock para una propuesta de venta corporativa."""
        # Consultar disponibilidad al agente de inventarios
        availability = self.inventory_agent.call_tool("check_stock_availability", items=requested_items)
        
        total_deal_revenue = 0.0
        total_deal_cost = 0.0
        details = []

        for item in requested_items:
            sku = item.get("sku")
            qty = item.get("quantity", 0)
            stock_info = self.inventory_agent.call_tool("get_stock_by_sku", sku=sku)
            if stock_info:
                rev = stock_info["sale_price"] * qty
                cost = stock_info["cost_price"] * qty
                total_deal_revenue += rev
                total_deal_cost += cost
                details.append({
                    "sku": sku,
                    "name": stock_info["name"],
                    "quantity": qty,
                    "unit_price": stock_info["sale_price"],
                    "subtotal": rev,
                    "available_in_stock": stock_info["total_available"],
                    "lead_time_days": stock_info["lead_time_days"],
                    "can_fulfill_immediately": stock_info["total_available"] >= qty
                })

        gross_margin = total_deal_revenue - total_deal_cost
        margin_pct = round((gross_margin / max(total_deal_revenue, 1.0)) * 100, 1)

        is_feasible = availability["all_items_sufficient"]
        recommendation = (
            "APROBADO PARA DESPACHO INMEDIATO: Todos los productos tienen existencias suficientes en almacén."
            if is_feasible else
            "APROBADO CON CONDICIÓN DE ENTREGA DIFERIDA: Hay productos con déficit de stock inmediato. Se debe emitir orden urgente a proveedores antes de confirmar fecha de entrega."
        )

        return {
            "client_name": client_name,
            "is_feasible_immediately": is_feasible,
            "total_deal_revenue": round(total_deal_revenue, 2),
            "estimated_gross_margin": round(gross_margin, 2),
            "margin_percentage": margin_pct,
            "cio_recommendation": recommendation,
            "items_evaluation": details,
            "availability_check": availability
        }

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_message(sender="DirectorGeneral", recipient=self.name, content=user_query)
        q = user_query.lower()

        # Ruteo inteligente y síntesis
        if any(w in q for w in ["informe", "reporte", "ejecutivo", "briefing", "estado general", "direccion"]):
            briefing = self.generate_executive_briefing()
            summary = f"El CIO ha consolidado el Informe Ejecutivo Corporativo al {briefing.generated_at}."
            recs = [alert.recommended_action for alert in briefing.cross_functional_alerts] + briefing.strategic_initiatives[:2]
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"briefing": briefing.dict()},
                recommendations=recs
            )

        elif any(w in q for w in ["simular", "factibilidad", "pedido nuevo", "podemos vender", "viabilidad"]):
            # Ejemplo de simulación de venta
            sample_items = [
                {"sku": "SKU-LAP-PRO16", "quantity": 10},
                {"sku": "SKU-MON-4K32", "quantity": 15},
                {"sku": "SKU-SEC-FIREWALL", "quantity": 5}
            ]
            sim = self.simulate_deal_feasibility(sample_items, client_name="Licitación Corporativa")
            status_text = "VIABLE INMEDIATAMENTE" if sim["is_feasible_immediately"] else "REQUIERE REABASTECIMIENTO PREVIO"
            summary = (
                f"Evaluación del CIO para propuesta de venta (${sim['total_deal_revenue']:,} con margen del {sim['margin_percentage']}%): "
                f"Dictamen: {status_text}."
            )
            resp = AgentResponse(
                agent_name=self.name,
                status="success" if sim["is_feasible_immediately"] else "warning",
                summary=summary,
                details={"simulation": sim},
                recommendations=[sim["cio_recommendation"]]
            )

        elif any(w in q for w in ["inventario", "stock", "almacen", "desabasto", "sku"]):
            # Delegar al subagente de inventarios y sintetizar
            inv_res = self.inventory_agent.handle_request(user_query, context)
            summary = f"[CIO -> Agente de Inventarios]: {inv_res.summary}"
            resp = AgentResponse(
                agent_name=self.name,
                status=inv_res.status,
                summary=summary,
                details={"delegated_to": self.inventory_agent.name, "response": inv_res.dict()},
                recommendations=inv_res.recommendations
            )

        elif any(w in q for w in ["venta", "comercial", "ingreso", "facturacion", "cliente", "pedido"]):
            # Delegar al subagente de ventas y sintetizar
            sales_res = self.sales_agent.handle_request(user_query, context)
            summary = f"[CIO -> Agente de Ventas]: {sales_res.summary}"
            resp = AgentResponse(
                agent_name=self.name,
                status=sales_res.status,
                summary=summary,
                details={"delegated_to": self.sales_agent.name, "response": sales_res.dict()},
                recommendations=sales_res.recommendations
            )

        else:
            # Respuesta holística del CIO
            briefing = self.generate_executive_briefing()
            summary = (
                f"Director de Información (CIO - CTIN): Supervisando operaciones activas. "
                f"Ingresos totales registrados: ${briefing.sales_kpis.get('total_revenue', 0):,} en {briefing.sales_kpis.get('total_orders', 0)} órdenes. "
                f"Existencias físicas: {briefing.inventory_kpis.get('total_units_on_hand', 0)} unidades. "
                f"Alertas de riesgo cruzado activas: {len(briefing.cross_functional_alerts)}."
            )
            resp = AgentResponse(

                agent_name=self.name,
                status="success",
                summary=summary,
                details={"briefing": briefing.dict()},
                recommendations=briefing.strategic_initiatives
            )

        self.log_message(sender=self.name, recipient="DirectorGeneral", content=resp.summary)
        return resp
