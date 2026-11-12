"""
enterprise_agents.api
Servicio API REST con FastAPI para interactuar con el CIO y los agentes de Ventas e Inventario.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
from enterprise_agents.database import init_database
from enterprise_agents.agents.cio_orchestrator import CIOAgent
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent
from enterprise_agents.models import ExecutiveBriefing, AgentResponse


# Inicializar base de datos
init_database()

app = FastAPI(
    title="CTIN Enterprise Multi-Agent CIO System",
    description="Sistema Multi-Agente Empresarial CTIN con CIO, Gestor de Ventas y Gestor de Inventario",
    version="1.0.0"
)


cio_agent = CIOAgent()
sales_agent = SalesAgent()
inventory_agent = InventoryAgent()


class ChatQueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


class DealSimulationRequest(BaseModel):
    client_name: str = "Cliente Corporativo"
    items: List[Dict[str, Any]]  # [{"sku": "SKU-LAP-PRO16", "quantity": 5}]


@app.get("/")
def root():
    return {
        "system": "Enterprise Multi-Agent CIO Ecosystem",
        "status": "online",
        "agents": [
            {"name": cio_agent.name, "role": cio_agent.role},
            {"name": sales_agent.name, "role": sales_agent.role},
            {"name": inventory_agent.name, "role": inventory_agent.role},
        ],
        "endpoints": {
            "executive_briefing": "/api/cio/executive-report",
            "chat_cio": "/api/cio/chat",
            "chat_sales": "/api/sales/chat",
            "chat_inventory": "/api/inventory/chat",
            "simulate_deal": "/api/simulate-deal"
        }
    }


@app.get("/api/cio/executive-report", response_model=ExecutiveBriefing)
def get_executive_report():
    """Genera y retorna el informe ejecutivo consolidado del CIO."""
    return cio_agent.generate_executive_briefing()


@app.post("/api/cio/chat", response_model=AgentResponse)
def chat_with_cio(payload: ChatQueryRequest):
    """Consulta directa al Director de Información (CIO), quien coordina con sus agentes subordinados."""
    return cio_agent.handle_request(payload.query, payload.context)


@app.post("/api/sales/chat", response_model=AgentResponse)
def chat_with_sales(payload: ChatQueryRequest):
    """Consulta directa al Agente de Ventas."""
    return sales_agent.handle_request(payload.query, payload.context)


@app.post("/api/inventory/chat", response_model=AgentResponse)
def chat_with_inventory(payload: ChatQueryRequest):
    """Consulta directa al Agente de Inventarios."""
    return inventory_agent.handle_request(payload.query, payload.context)


@app.post("/api/simulate-deal")
def simulate_deal(payload: DealSimulationRequest):
    """El CIO evalúa la viabilidad comercial y operativa de una propuesta de venta."""
    return cio_agent.simulate_deal_feasibility(payload.items, payload.client_name)

