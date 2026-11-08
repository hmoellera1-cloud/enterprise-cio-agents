"""
enterprise_agents.agents.sales_agent
Agente especialista en gestión, auditoría y análisis de información de ventas.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from enterprise_agents.agents.base_agent import BaseAgent
from enterprise_agents.models import AgentResponse
from enterprise_agents.tools import sales_tools


class SalesAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SalesAgent",
            role="Director de Información de Ventas",
            description="Gestiona y analiza transacciones comerciales, clientes, historial de pedidos e ingresos.",
            system_prompt="""
Eres el Agente Gestor de Ventas de la empresa.
Proporcionas análisis cuantitativo sobre ingresos, volumen de pedidos, productos estrella y regiones.
Tus respuestas son concisas, estructuradas y con enfoque en métricas y cumplimiento comercial.
"""
        )
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(sales_tools.get_sales_kpis, "get_sales_kpis")
        self.register_tool(sales_tools.get_top_selling_products, "get_top_selling_products")
        self.register_tool(sales_tools.get_sales_by_region, "get_sales_by_region")
        self.register_tool(sales_tools.get_sales_by_category, "get_sales_by_category")
        self.register_tool(sales_tools.get_recent_orders, "get_recent_orders")
        self.register_tool(sales_tools.get_sales_pipeline_insights, "get_sales_pipeline_insights")
        self.register_tool(sales_tools.search_product_sales, "search_product_sales")

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_message(sender="UserOrCIO", recipient=self.name, content=user_query)
        q = user_query.lower()

        # Detección de mes si aplica
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        found_month = next((m for m in months if m in q), None)

        # Palabras de búsqueda de producto específico
        search_indicators = [
            "cuantas", "cuantos", "cuanta", "cuanto", "cuántas", "cuántos", "cuánta", "cuánto",
            "vendieron", "vendio", "vendió", "buscar", "modelo", "westin"
        ]
        is_search = any(w in q for w in search_indicators) or ("venta de " in q or "ventas de " in q)

        stopwords = {
            "cuantas", "cuantos", "cuanta", "cuanto", "cuántas", "cuántos", "cuánta", "cuánto",
            "se", "vendieron", "vendio", "vendió", "en", "el", "la", "los", "las",
            "un", "una", "unos", "unas", "de", "del", "por", "favor", "dime", "diga", "mes", "ano", "año", "para",
            "total", "sobre", "ventas", "venta", "pedidos", "ordenes", "órdenes", "informacion", "información",
            "hay", "buscar", "modelo"
        }
        if found_month:
            stopwords.add(found_month)

        clean_text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in q)
        candidate_tokens = [w for w in clean_text.split() if w not in stopwords]
        extracted_keyword = " ".join(candidate_tokens).strip()

        # Análisis semántico de la consulta
        # 1. Búsqueda de producto si hay término identificado y no es un pedido de KPI global
        product_result = None
        if extracted_keyword and not any(w in q for w in ["kpi", "resumen general", "facturacion total", "pipeline"]):
            res = self.call_tool("search_product_sales", keyword=extracted_keyword, month=found_month)
            if res.get("total_units_sold", 0) > 0 or is_search:
                product_result = res

        if product_result:
            result = product_result
            period_str = f"en {found_month.capitalize()}" if found_month else "en el período registrado de CTIN"

            if result["total_units_sold"] > 0:
                summary = (
                    f"Ventas de '{extracted_keyword}' {period_str}: "
                    f"Se vendieron un total de {result['total_units_sold']} unidades "
                    f"por un valor de ${result['total_revenue']:,} USD a través de {result['total_variants']} variantes de producto."
                )
                recs = [
                    f"Variante líder: '{result['variants'][0]['name']}' ({result['variants'][0]['units_sold']} uds vendidas, ${result['variants'][0]['revenue']:,} USD).",
                    "Coordinar con el Director de Inventarios para auditar existencias y órdenes de reposición en bodegas."
                ]
            else:
                summary = f"No se registraron ventas para '{extracted_keyword}' {period_str}."
                recs = [
                    "Verificar si la denominación exacta o código SKU figura en el catálogo maestro de CTIN."
                ]

            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"search_result": result},
                recommendations=recs
            )

        elif any(w in q for w in ["kpi", "resumen", "total", "ingreso", "facturacion", "general"]):
            kpis = self.call_tool("get_sales_kpis")
            pipeline = self.call_tool("get_sales_pipeline_insights")
            summary = (
                f"Facturación Total: ${kpis['total_revenue']:,} en {kpis['total_orders']} pedidos. "
                f"Ticket promedio: ${kpis['average_order_value']:,}. "
                f"Pedidos completados: {kpis['completed_orders']}, en proceso: {kpis['processing_orders']}, pendientes: {kpis['pending_orders']}."
            )
            recs = [
                "Priorizar despacho de los pedidos en estado PENDING y PROCESSING.",
                f"Acelerar conversión del pipeline activo valorado en ${pipeline['committed_or_pending_revenue']:,}."
            ]

            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"kpis": kpis, "pipeline": pipeline},
                recommendations=recs
            )

        elif any(w in q for w in ["top", "estrella", "mas vendido", "populares", "productos"]):
            top = self.call_tool("get_top_selling_products", limit=5)
            summary = f"Identificados los top {len(top)} productos por recaudación comercial."
            recs = []
            for item in top:
                if item["stock_status"] in ["WARNING", "CRITICAL"]:
                    recs.append(f"ALERTA: El producto líder '{item['name']}' tiene stock {item['stock_status']} ({item['stock_available']} disp). Requiere coordinación con Inventario.")
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"top_products": top},
                recommendations=recs or ["Mantener promociones en el mix de productos de mayor margen."]
            )

        elif any(w in q for w in ["region", "zona", "geografico", "territorio"]):
            by_region = self.call_tool("get_sales_by_region")
            by_cat = self.call_tool("get_sales_by_category")
            summary = "Desglose territorial y por categoría completado."
            top_region = max(by_region.items(), key=lambda x: x[1]) if by_region else ("N/A", 0)
            recs = [
                f"Región con mayor tracción: {top_region[0]} (${top_region[1]:,}).",
                "Explorar campañas de penetración en zonas de menor cuota."
            ]
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"sales_by_region": by_region, "sales_by_category": by_cat},
                recommendations=recs
            )

        elif any(w in q for w in ["pedido", "orden", "reciente", "ultimos"]):
            orders = self.call_tool("get_recent_orders", limit=5)
            summary = f"Se obtuvieron los {len(orders)} pedidos corporativos más recientes."
            recs = ["Verificar tiempos de entrega con los centros de distribución."]
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"recent_orders": orders},
                recommendations=recs
            )

        else:
            # Respuesta holística por defecto
            kpis = self.call_tool("get_sales_kpis")
            top = self.call_tool("get_top_selling_products", limit=3)
            summary = f"Resumen comercial consolidado: Facturación acumulada de ${kpis['total_revenue']:,}."
            resp = AgentResponse(

                agent_name=self.name,
                status="success",
                summary=summary,
                details={"kpis": kpis, "top_products": top},
                recommendations=["Revisar periódicamente la alineación con stock en almacenes."]
            )

        self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
        return resp
