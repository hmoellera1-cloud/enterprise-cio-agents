"""
enterprise_agents.agents.sales_agent
Agente especialista en gestión, auditoría y análisis de información de ventas.
"""

from __future__ import annotations
import datetime
import re
import unicodedata
from typing import Any, Dict, List, Optional
from enterprise_agents.agents.base_agent import BaseAgent
from enterprise_agents.models import AgentResponse
from enterprise_agents.tools import sales_tools


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )


class SalesAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SalesAgent",
            role="Director de Información de Ventas",
            description="Gestiona y analiza transacciones comerciales, clientes, historial de pedidos, precios, costos e ingresos.",
            system_prompt="""
Eres el Agente Gestor de Ventas de CTIN.
Proporcionas análisis cuantitativo sobre ingresos, volumen de pedidos, precios, costos de materia prima, márgenes, clientes y productos.
Tus respuestas son concisas, estructuradas y con enfoque en métricas reales en $ USD.
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
        self.register_tool(sales_tools.get_sales_by_date, "get_sales_by_date")
        self.register_tool(sales_tools.get_margin_analysis, "get_margin_analysis")
        self.register_tool(sales_tools.get_sales_by_month, "get_sales_by_month")
        self.register_tool(sales_tools.get_top_customers, "get_top_customers")
        self.register_tool(sales_tools.get_sales_by_date_range, "get_sales_by_date_range")

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        self.log_message(sender="UserOrCIO", recipient=self.name, content=user_query)
        q = _strip_accents(user_query)

        # Extraer posible límite (ej. "top 10")
        top_match = re.search(r"\btop\s+(\d+)\b", q)
        limit_n = min(max(int(top_match.group(1)), 1), 25) if top_match else 6

        # 0. Consultas por rango de fechas o fecha puntual (ayer, hoy, semana pasada, YYYY-MM-DD, última fecha)
        explicit_date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", q)
        if "semana pasada" in q or "ultimos 7 dias" in q or "ultima semana" in q:
            today = datetime.date.today()
            end_d = today.isoformat()
            start_d = (today - datetime.timedelta(days=7)).isoformat()
            r_res = self.call_tool("get_sales_by_date_range", start_date=start_d, end_date=end_d)
            if r_res["orders_count"] == 0 and r_res.get("latest_date"):
                # Mostrar los últimos 7 días disponibles respecto a la última fecha sincronizada
                latest_dt = datetime.date.fromisoformat(r_res["latest_date"])
                alt_start = (latest_dt - datetime.timedelta(days=6)).isoformat()
                alt_res = self.call_tool("get_sales_by_date_range", start_date=alt_start, end_date=r_res["latest_date"])
                summary = (
                    f"No hay ventas en los últimos 7 días calendario ({start_d} a {end_d}). "
                    f"En la última semana con datos sincronizados ({alt_start} a {r_res['latest_date']}): "
                    f"{alt_res['orders_count']} pedidos por ${alt_res['total_revenue']:,} USD."
                )
                details = {"search_result": {"variants": alt_res["variants"]}}
            else:
                summary = (
                    f"Ventas de los últimos 7 días ({start_d} a {end_d}): "
                    f"{r_res['orders_count']} pedidos, {r_res['total_units_sold']} unidades por ${r_res['total_revenue']:,} USD."
                )
                details = {"search_result": {"variants": r_res["variants"]}}
            resp = AgentResponse(agent_name=self.name, status="success", summary=summary, details=details, recommendations=[])
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        date_keywords = ["ayer", "hoy", "anteayer", "antier", "ultima fecha", "ultimo dia"]
        if explicit_date_match or any(w in q.split() or w in q for w in date_keywords if len(w) > 3 or w in q.split()):
            today = datetime.date.today()
            if explicit_date_match:
                target_date = explicit_date_match.group(1)
                date_label = target_date
            elif "anteayer" in q or "antier" in q:
                target_date = (today - datetime.timedelta(days=2)).isoformat()
                date_label = f"anteayer ({target_date})"
            elif re.search(r"\bayer\b", q):
                target_date = (today - datetime.timedelta(days=1)).isoformat()
                date_label = f"ayer ({target_date})"
            elif re.search(r"\bhoy\b", q):
                target_date = today.isoformat()
                date_label = f"hoy ({target_date})"
            else:
                target_date = "LATEST"
                date_label = "la última fecha disponible"

            if target_date == "LATEST":
                probe = self.call_tool("get_sales_by_date", target_date="9999-12-31")
                latest = probe.get("latest_available")
                if latest:
                    summary = (
                        f"Última fecha con ventas sincronizadas en CTIN ({latest['date']}): "
                        f"{latest['orders_count']} pedidos por ${latest['total_revenue']:,} USD "
                        f"({latest['total_units_sold']} unidades en los productos principales)."
                    )
                    details = {"search_result": {"variants": latest["variants"]}}
                else:
                    summary = "No hay ventas registradas en la base de datos de CTIN."
                    details = {}
            else:
                date_res = self.call_tool("get_sales_by_date", target_date=target_date)
                if date_res["orders_count"] > 0:
                    summary = (
                        f"Ventas de {date_label}: {date_res['orders_count']} pedidos, "
                        f"{date_res['total_units_sold']} unidades vendidas por un total de ${date_res['total_revenue']:,} USD."
                    )
                    details = {"search_result": {"variants": date_res["variants"]}}
                else:
                    latest = date_res.get("latest_available")
                    if latest:
                        summary = (
                            f"No hay ventas registradas para {date_label}. "
                            f"La última fecha sincronizada en la base de datos de CTIN es {latest['date']}, "
                            f"donde se registraron {latest['orders_count']} pedidos por ${latest['total_revenue']:,} USD."
                        )
                        details = {"search_result": {"variants": latest["variants"]}}
                    else:
                        summary = f"No hay ventas registradas para {date_label}."
                        details = {}

            resp = AgentResponse(agent_name=self.name, status="success", summary=summary, details=details, recommendations=[])
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 1. Clientes principales
        if any(w in q for w in ["cliente", "clientes", "comprador", "compradores", "quien compra"]):
            custs = self.call_tool("get_top_customers", limit=limit_n)
            top_c = custs[0] if custs else None
            summary = (
                f"Top {len(custs)} clientes de CTIN por facturación. "
                + (f"Cliente #1: {top_c['name']} con ${top_c['revenue']:,} USD en {top_c['units_sold']} pedidos." if top_c else "")
            )
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"customers": custs, "search_result": {"variants": custs}},
                recommendations=[]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # Detección de mes
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        found_month = next((m for m in months if re.search(rf"\b{m}\b", q)), None)

        # Limpieza de stopwords para extraer posible producto específico
        stopwords = {
            "que", "cual", "cuales", "como", "cuando", "donde", "quien", "quienes",
            "cuantas", "cuantos", "cuanta", "cuanto", "cuesta", "cuestan", "vale", "valen", "hacer", "fabricar",
            "se", "vendieron", "vendio", "vende", "venden", "vendida", "vendidas", "vendido", "vendidos",
            "en", "el", "la", "los", "las", "y", "o", "es", "son", "esta", "estan", "tiene", "tienen", "hay",
            "un", "una", "unos", "unas", "de", "del", "por", "favor", "dime", "diga", "dame", "muestra", "mostrar",
            "mes", "meses", "ano", "anos", "para", "total", "sobre", "ventas", "venta", "pedidos", "ordenes",
            "informacion", "buscar", "modelo", "producto", "productos", "top", "estrella", "mas", "mayor", "mejor",
            "populares", "popular", "precio", "precios", "margen", "margenes", "materia", "prima", "costo", "costos",
            "rentabilidad", "ganancia", "utilidad", "bruto", "bruta", "general", "generales", "resumen", "kpi", "kpis",
            "todo", "toda", "todos", "todas", "lista", "catalogo"
        }
        if found_month:
            stopwords.add(found_month)
        if top_match:
            stopwords.add(top_match.group(1))

        clean_text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in q)
        candidate_tokens = [w for w in clean_text.split() if w not in stopwords and not w.isdigit()]
        extracted_keyword = " ".join(candidate_tokens).strip()

        # 2. Consultas de "producto más vendido" / "top N"
        is_top_query = any(w in q for w in ["top", "estrella", "mas vendido", "mas vendida", "mas vendidos", "mas vendidas", "populares"])
        if is_top_query:
            if extracted_keyword:
                # Ej: "cual es la sala mas vendida?"
                res = self.call_tool("search_product_sales", keyword=extracted_keyword, month=found_month)
                if res["total_units_sold"] > 0:
                    leader = res["variants"][0]
                    period_str = f"en {found_month.capitalize()}" if found_month else "en el período registrado"
                    summary = (
                        f"Producto más vendido de '{extracted_keyword}' {period_str}: "
                        f"'{leader['name']}' con {leader['units_sold']} unidades por ${leader['revenue']:,} USD "
                        f"(margen {leader['margin_pct']}%). Total línea: {res['total_units_sold']} uds / ${res['total_revenue']:,} USD."
                    )
                    resp = AgentResponse(
                        agent_name=self.name,
                        status="success",
                        summary=summary,
                        details={"search_result": res},
                        recommendations=[]
                    )
                    self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
                    return resp

            top = self.call_tool("get_top_selling_products", limit=limit_n)
            leader = top[0] if top else None
            variants_top = [
                {"sku": t["sku"], "name": t["name"], "units_sold": t["units_sold"], "revenue": t["revenue"]}
                for t in top
            ]
            summary = (
                f"Top {len(top)} productos más vendidos por facturación en CTIN. "
                + (f"Líder: '{leader['name']}' con {leader['units_sold']} uds (${leader['revenue']:,} USD)." if leader else "")
            )
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"top_products": top, "search_result": {"variants": variants_top}},
                recommendations=[]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 3. Búsqueda de producto específico (ej. "salas westin", "precio de sala westin", "cuanto cuesta hacer sala westin")
        if extracted_keyword and not any(w in q for w in ["region", "zona", "territorio", "categoria", "pipeline"]):
            res = self.call_tool("search_product_sales", keyword=extracted_keyword, month=found_month)
            if res["total_units_sold"] > 0:
                avg_unit = round(res["total_revenue"] / res["total_units_sold"], 2)
                period_str = f"en {found_month.capitalize()}" if found_month else "en el período registrado de CTIN"
                summary = (
                    f"Ventas de '{extracted_keyword}' {period_str}: "
                    f"{res['total_units_sold']} unidades vendidas por ${res['total_revenue']:,} USD "
                    f"(precio promedio: ${avg_unit:,} USD) en {res['total_variants']} variantes. "
                    f"Costo materia prima/producción: ${res['total_cost']:,} USD | "
                    f"Margen bruto: ${res['gross_margin']:,} USD ({res['margin_pct']}%)."
                )
                resp = AgentResponse(
                    agent_name=self.name,
                    status="success",
                    summary=summary,
                    details={"search_result": res},
                    recommendations=[]
                )
                self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
                return resp

        # 4. Ventas por mes (ej. "cuanto se vendio en octubre?", "ventas por mes")
        if found_month or "por mes" in q or "mensual" in q:
            m_res = self.call_tool("get_sales_by_month", month=found_month)
            if found_month:
                summary = (
                    f"Ventas de {found_month.capitalize()} en CTIN: "
                    f"{m_res['orders_count']} pedidos, {m_res['total_units_sold']:,} unidades vendidas por ${m_res['total_revenue']:,} USD. "
                    f"Costo materia prima: ${m_res['total_cost']:,} USD | Margen bruto: ${m_res['gross_margin']:,} USD ({m_res['margin_pct']}%)."
                )
                variants = m_res["variants"]
            else:
                months_list = m_res["months"]
                summary = f"Resumen de ventas mensuales de CTIN ({len(months_list)} meses registrados)."
                variants = months_list
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"monthly_sales": m_res, "search_result": {"variants": variants}},
                recommendations=[]
            )
            self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
            return resp

        # 5. Análisis global de márgenes, costos y precios
        if any(w in q for w in ["margen", "materia prima", "rentabilidad", "ganancia", "utilidad", "costo", "precio"]):
            margin = self.call_tool("get_margin_analysis", limit=limit_n)
            summary = (
                f"Análisis de Márgenes y Costos CTIN: Sobre ventas con costo registrado de ${margin['costed_revenue']:,} USD "
                f"(facturación total ${margin['total_revenue']:,} USD), el costo de materia prima/producción es ${margin['total_cost']:,} USD, "
                f"generando un margen bruto de ${margin['gross_margin']:,} USD ({margin['margin_pct']}%)."
            )
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"margin_analysis": margin, "search_result": {"variants": margin["variants"]}},
                recommendations=[]
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

        elif any(w in q for w in ["region", "zona", "geografico", "territorio", "categoria"]):
            by_region = self.call_tool("get_sales_by_region")
            by_cat = self.call_tool("get_sales_by_category")
            summary = "Desglose territorial y por categoría completado."
            variants = [{"sku": k, "name": k, "units_sold": 0, "revenue": v} for k, v in list(by_cat.items())[:8]]
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"sales_by_region": by_region, "sales_by_category": by_cat, "search_result": {"variants": variants}},
                recommendations=[]
            )

        elif any(w in q for w in ["pedido", "orden", "reciente", "ultimos"]):
            orders = self.call_tool("get_recent_orders", limit=limit_n)
            summary = f"Se obtuvieron los {len(orders)} pedidos corporativos más recientes."
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"recent_orders": orders},
                recommendations=[]
            )

        else:
            kpis = self.call_tool("get_sales_kpis")
            top = self.call_tool("get_top_selling_products", limit=3)
            summary = f"Resumen comercial consolidado: Facturación acumulada de ${kpis['total_revenue']:,} en {kpis['total_orders']} pedidos."
            resp = AgentResponse(
                agent_name=self.name,
                status="success",
                summary=summary,
                details={"kpis": kpis, "top_products": top},
                recommendations=[]
            )

        self.log_message(sender=self.name, recipient="UserOrCIO", content=resp.summary)
        return resp
