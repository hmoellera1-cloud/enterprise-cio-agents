"""
enterprise_agents.agents.inventory_agent
Agente especialista en supervisión de stock, almacenes, alertas y reabastecimiento.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from enterprise_agents.agents.base_agent import BaseAgent
from enterprise_agents.models import AgentResponse
from enterprise_agents.tools import inventory_tools


class InventoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="InventoryAgent",
            role="Director de Información de Inventarios",
            description="Supervisa existencias en almacenes, rotación, niveles de seguridad y solicitudes de reabastecimiento.",
            system_prompt="""
Eres el Agente Gestor de Inventarios de la empresa.
Monitoreas los niveles de existencia en los almacenes, identificas desabastos críticos y emites órdenes de reposición.
Priorizas la continuidad operativa, minimizando quiebres de stock sin incurrir en sobrecostes de almacenamiento.
"""
        )
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(inventory_tools.get_inventory_kpis, "get_inventory_kpis")
        self.register_tool(inventory_tools.get_critical_stock_alerts, "get_critical_stock_alerts")
        self.register_tool(inventory_tools.get_stock_by_sku, "get_stock_by_sku")
        self.register_tool(inventory_tools.create_restock_request, "create_restock_request")
        self.register_tool(inventory_tools.check_stock_availability, "check_stock_availability")
        self.register_tool(inventory_tools.search_inventory_by_keyword, "search_inventory_by_keyword")

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_message(sender="UserOrCIO", recipient=self.name, content=user_query)
        q = user_query.lower()

        # Análisis semántico de la consulta
        if any(w in q for w in ["alerta", "critico", "bajo", "desabasto", "seguridad", "urgente"]):
            alerts = self.call_tool("get_critical_stock_alerts")
            critical_count = sum(1 for a in alerts if a["urgency"] == "CRITICAL")
            warning_count = sum(1 for a in alerts if a["urgency"] == "WARNING")
            summary = (
                f"Auditoría de Almacén: Se detectaron {len(alerts)} productos en riesgo "
                f"({critical_count} CRÍTICOS y {warning_count} en nivel de reorden)."
            )
            recs = [
                f"Emitir orden de compra inmediata para {a['name']} ({a['sku']}) con {a['recommended_restock_qty']} unidades."
                for a in alerts if a["urgency"] == "CRITICAL"
            ]
            resp = AgentResponse(
                agent_name=self.name,
                status="warning" if alerts else "success",
                summary=summary,
                details={"alerts": alerts, "critical_count": critical_count, "warning_count": warning_count},
                recommendations=recs or ["Niveles de inventario estables."]
            )

        elif any(w in q for w in ["resumen", "total", "almacen", "kpi", "valoracion", "general"]):
            kpis = self.call_tool("get_inventory_kpis")
            alerts = self.call_tool("get_critical_stock_alerts")
            summary = (
                f"Inventario Global: {kpis['total_skus']} SKUs activos, "
                f"{kpis['total_units_on_hand']} unidades físicas (${kpis['total_valuation_cost']:,} coste / ${kpis['total_valuation_retail']:,} venta). "
                f"Unidades disponibles no comprometidas: {kpis['total_units_available']}."
            )

            recs = [
                f"Atender {len(alerts)} SKUs que requieren reposición.",
                "Mantener balance de ocupación en los 3 centros de distribución."
            ]
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"kpis": kpis, "alerts_count": len(alerts)},
                recommendations=recs
            )

        elif any(w in q for w in ["sku", "producto", "especifico", "consultar"]) or (
            not any(w in q for w in ["reorden", "reabastecer", "comprar", "pedido proveedor"])
            and any(w in q for w in ["stock", "inventario", "existencia", "existencias", "cuanto", "cuánto", "cuantos", "cuántos", "hay", "bodega", "almacen", "almacén"])
        ):
            import re
            sku_match = re.search(r"SKU-[A-Z0-9\-]+", user_query.upper())
            if sku_match:
                target_sku = sku_match.group(0)
                stock = self.call_tool("get_stock_by_sku", sku=target_sku)
                if stock:
                    summary = (
                        f"Ficha de SKU {target_sku} ({stock['name']}): "
                        f"Físico: {stock['total_on_hand']} | Reservado: {stock['total_reserved']} | "
                        f"Disponible: {stock['total_available']} | Mínimo seguridad: {stock['min_safety_stock']}."
                    )
                    recs = [
                        f"Tiempo de entrega de proveedor: {stock['lead_time_days']} días.",
                        "Estado: " + ("CRÍTICO" if stock['total_available'] <= stock['min_safety_stock'] else "NORMAL")
                    ]
                    resp = AgentResponse(
                        agent_name=self.name,
                        status="success",
                        summary=summary,
                        details={"stock": stock},
                        recommendations=recs
                    )
                else:
                    resp = AgentResponse(
                        agent_name=self.name,
                        status="error",
                        summary=f"No se encontró información para el SKU '{target_sku}'.",
                        recommendations=["Verificar el código de SKU solicitado."]
                    )
            else:
                inv_stop = {
                    "que", "qué", "cual", "cuál", "cuanto", "cuánto", "cuantos", "cuántos", "cuantas", "cuántas",
                    "stock", "inventario", "existencia", "existencias", "hay", "tiene", "tienen", "de", "del",
                    "en", "el", "la", "los", "las", "un", "una", "bodega", "bodegas", "almacen", "almacén",
                    "consultar", "producto", "sku", "sobre", "por", "favor"
                }
                clean_text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in q)
                kw = " ".join(w for w in clean_text.split() if w not in inv_stop).strip()
                if kw:
                    inv_res = self.call_tool("search_inventory_by_keyword", keyword=kw)
                    if inv_res["total_variants"] > 0:
                        summary = (
                            f"Inventario de '{kw}' en CTIN ({inv_res['total_variants']} variantes): "
                            f"Stock físico: {inv_res['total_on_hand']:,} uds | Reservado: {inv_res['total_reserved']:,} uds | "
                            f"Disponible: {inv_res['total_available']:,} uds (valoración al costo: ${inv_res['total_cost_valuation']:,} USD)."
                        )
                        resp = AgentResponse(
                            agent_name=self.name,
                            status="success",
                            summary=summary,
                            details={"inventory_search": inv_res, "search_result": {"variants": inv_res["variants"]}},
                            recommendations=["Revisar bodegas con disponibilidad inmediata para despacho."]
                        )
                    else:
                        resp = AgentResponse(
                            agent_name=self.name,
                            status="success",
                            summary=f"No se encontraron existencias en inventario para '{kw}'.",
                            recommendations=["Verificar el nombre o código SKU en el catálogo de CTIN."]
                        )
                else:
                    kpis = self.call_tool("get_inventory_kpis")
                    summary = (
                        f"Inventario Global: {kpis['total_skus']} SKUs activos, "
                        f"{kpis['total_units_on_hand']:,} unidades físicas (${kpis['total_valuation_cost']:,} coste / ${kpis['total_valuation_retail']:,} venta). "
                        f"Disponibles: {kpis['total_units_available']:,}."
                    )
                    resp = AgentResponse(
                        agent_name=self.name,
                        status="success",
                        summary=summary,
                        details={"kpis": kpis},
                        recommendations=[]
                    )

        elif any(w in q for w in ["reorden", "reabastecer", "comprar", "pedido proveedor"]):
            # Disparar solicitudes de reabastecimiento para críticos
            alerts = self.call_tool("get_critical_stock_alerts")
            actions = []
            for alert in alerts:
                res = self.call_tool(
                    "create_restock_request",
                    sku=alert["sku"],
                    quantity=alert["recommended_restock_qty"],
                    urgency=alert["urgency"],
                    reason=alert["message"]
                )
                actions.append(res)
            summary = f"Se generaron {len(actions)} órdenes de reabastecimiento automáticas en almacén central."
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"restock_orders": actions},
                recommendations=["Notificar al equipo de adquisiciones y seguimiento de proveedores."]
            )

        else:
            kpis = self.call_tool("get_inventory_kpis")
            alerts = self.call_tool("get_critical_stock_alerts")
            summary = f"Supervisión de almacenes activa. Unidades disponibles: {kpis['total_units_available']}. Alertas: {len(alerts)}."
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"kpis": kpis, "alerts": alerts},
                recommendations=["Revisar detalle de alertas con la consulta 'alertas de inventario'."]
            )

        self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
        return resp
