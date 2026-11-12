"""
enterprise_agents.agents.inventory_agent
Agente especialista en supervisión de stock, almacenes, alertas y reabastecimiento.
"""

from __future__ import annotations
import re
import unicodedata
from typing import Any, Dict, List, Optional
from enterprise_agents.agents.base_agent import BaseAgent
from enterprise_agents.models import AgentResponse
from enterprise_agents.tools import inventory_tools


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )


class InventoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="InventoryAgent",
            role="Director de Información de Inventarios",
            description="Supervisa existencias en almacenes, rotación, niveles de seguridad y solicitudes de reabastecimiento.",
            system_prompt="""
Eres el Agente Gestor de Inventarios de CTIN.
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
        self.register_tool(inventory_tools.get_warehouses_summary, "get_warehouses_summary")
        self.register_tool(inventory_tools.get_out_of_stock_products, "get_out_of_stock_products")

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_message(sender="UserOrCIO", recipient=self.name, content=user_query)
        q = _strip_accents(user_query)

        # 1. Productos sin stock / agotados
        if any(p in q for p in ["sin stock", "sin existencia", "sin existencias", "agotado", "agotados", "stock cero", "cero stock"]):
            out_items = self.call_tool("get_out_of_stock_products", limit=15)
            summary = (
                f"Productos sin stock disponible en CTIN (top {len(out_items)} con mayor demanda histórica): "
                + (f"Principal afectado: '{out_items[0]['name']}' ({out_items[0]['units_sold']} uds vendidas históricamente)." if out_items else "")
            )
            resp = AgentResponse(
                agent_name=self.name,
                status="warning" if out_items else "success",
                summary=summary,
                details={"out_of_stock": out_items, "search_result": {"variants": out_items}},
                recommendations=["Evaluar reposición prioritaria de los SKUs sin stock con mayor rotación."]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 2. Alertas críticas de inventario
        if any(w in q for w in ["alerta", "critico", "criticos", "bajo", "desabasto", "seguridad", "urgente"]):
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
            variants = [
                {"sku": a["sku"], "name": a["name"], "units_sold": a["available_stock"], "revenue": 0}
                for a in alerts[:10]
            ]
            resp = AgentResponse(
                agent_name=self.name,
                status="warning" if alerts else "success",
                summary=summary,
                details={"alerts": alerts, "critical_count": critical_count, "warning_count": warning_count, "search_result": {"variants": variants}},
                recommendations=recs or ["Niveles de inventario estables."]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 3. Órdenes de reabastecimiento
        if any(w in q for w in ["reorden", "reabastecer", "comprar", "pedido proveedor"]):
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
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 4. Extraer posible producto específico (antes de asumir listado general)
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
                resp = AgentResponse(
                    agent_name=self.name,
                    status="success",
                    summary=summary,
                    details={"stock": stock},
                    recommendations=[f"Tiempo de entrega de proveedor: {stock['lead_time_days']} días."]
                )
            else:
                resp = AgentResponse(
                    agent_name=self.name,
                    status="error",
                    summary=f"No se encontró información para el SKU '{target_sku}'.",
                    recommendations=["Verificar el código de SKU solicitado."]
                )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        inv_stop = {
            "que", "cual", "cuales", "como", "donde", "cuanto", "cuanta", "cuantos", "cuantas",
            "vale", "valen", "cuesta", "cuestan", "todo", "toda", "todos", "todas",
            "stock", "inventario", "inventarios", "existencia", "existencias", "hay", "tiene", "tienen",
            "de", "del", "en", "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "es", "son",
            "bodega", "bodegas", "almacen", "almacenes", "consultar", "producto", "productos", "sku",
            "sobre", "por", "favor", "dime", "dame", "muestra", "mostrar", "resumen", "total", "kpi", "kpis",
            "valoracion", "general", "lista", "listado"
        }
        clean_text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in q)
        kw = " ".join(w for w in clean_text.split() if w not in inv_stop).strip()

        if kw:
            inv_res = self.call_tool("search_inventory_by_keyword", keyword=kw)
            if inv_res["total_variants"] > 0:
                wh_text = ""
                if inv_res.get("warehouses"):
                    top_wh = ", ".join(f"{w['name']} ({w['available']} disp)" for w in inv_res["warehouses"][:4])
                    wh_text = f" Bodegas principales: {top_wh}."
                summary = (
                    f"Inventario de '{kw}' en CTIN ({inv_res['total_variants']} variantes): "
                    f"Stock físico: {inv_res['total_on_hand']:,} uds | Reservado: {inv_res['total_reserved']:,} uds | "
                    f"Disponible: {inv_res['total_available']:,} uds (valoración al costo: ${inv_res['total_cost_valuation']:,} USD)."
                    f"{wh_text}"
                )
                resp = AgentResponse(
                    agent_name=self.name,
                    status="success",
                    summary=summary,
                    details={"inventory_search": inv_res, "search_result": {"variants": inv_res["variants"]}},
                    recommendations=["Revisar bodegas con disponibilidad inmediata para despacho."]
                )
                self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
                return resp

        # 5. Listado de bodegas / almacenes
        if any(w in q for w in ["bodega", "bodegas", "almacenes"]):
            wh = self.call_tool("get_warehouses_summary", limit=15)
            summary = f"CTIN cuenta con {wh['total_warehouses']} bodegas/almacenes registrados (mostrando los {len(wh['warehouses'])} con mayor inventario físico)."
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"warehouses": wh, "search_result": {"variants": wh["warehouses"]}},
                recommendations=[]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 6. Resumen / valoración global de inventario
        kpis = self.call_tool("get_inventory_kpis")
        alerts = self.call_tool("get_critical_stock_alerts")
        summary = (
            f"Inventario Global: {kpis['total_skus']} SKUs activos, "
            f"{kpis['total_units_on_hand']:,} unidades físicas (${kpis['total_valuation_cost']:,} USD coste / ${kpis['total_valuation_retail']:,} USD venta). "
            f"Unidades disponibles no comprometidas: {kpis['total_units_available']:,}."
        )
        resp = AgentResponse(
            agent_name=self.name,
            status="success",
            summary=summary,
            details={"kpis": kpis, "alerts_count": len(alerts)},
            recommendations=[f"Atender {len(alerts)} SKUs que requieren reposición."]
        )
        self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
        return resp
