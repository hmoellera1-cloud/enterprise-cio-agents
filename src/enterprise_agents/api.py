"""
enterprise_agents.api
Servicio API REST con FastAPI para interactuar con el CIO y los agentes de Ventas e Inventario.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
import urllib.parse
from enterprise_agents.database import init_database
from enterprise_agents.agents.cio_orchestrator import CIOAgent
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent
from enterprise_agents.models import ExecutiveBriefing, AgentResponse
from enterprise_agents.whatsapp_service import process_whatsapp_message, generate_twiml_response


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


@app.api_route("/api/whatsapp/webhook", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request):
    """
    Webhook universal para WhatsApp:
    - Si es POST de Twilio (form-urlencoded con 'Body' y 'From'), responde con TwiML XML.
    - Si es POST de Meta WhatsApp Cloud API (JSON), extrae el mensaje y responde 200.
    - Si es GET (Meta verification 'hub.challenge'), valida el token.
    """
    if request.method == "GET":
        # Verificación de Webhook para Meta WhatsApp Cloud API
        params = request.query_params
        mode = params.get("hub.mode")
        challenge = params.get("hub.challenge")
        token = params.get("hub.verify_token")
        if mode == "subscribe" and token == "cio_enterprise_secret_2026":
            return Response(content=challenge, media_type="text/plain")
        return {"status": "whatsapp webhook active"}

    # Procesar POST
    body_bytes = await request.body()
    content_type = request.headers.get("content-type", "")

    incoming_text = ""
    sender = ""

    if "application/json" in content_type:
        try:
            import json
            data = json.loads(body_bytes.decode("utf-8"))
            # Extraer formato Meta Cloud API
            entry = data.get("entry", [{}])[0]
            change = entry.get("changes", [{}])[0]
            value = change.get("value", {})
            messages = value.get("messages", [])
            if messages:
                incoming_text = messages[0].get("text", {}).get("body", "")
                sender = messages[0].get("from", "")
        except Exception:
            incoming_text = ""
    else:
        # Formato Twilio x-www-form-urlencoded
        try:
            parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))
            incoming_text = parsed.get("Body", [""])[0]
            sender = parsed.get("From", [""])[0]
        except Exception:
            incoming_text = body_bytes.decode("utf-8", errors="ignore")

    # Si no se detectó texto directo, intentar decodificar crudo
    if not incoming_text and body_bytes:
        incoming_text = body_bytes.decode("utf-8", errors="ignore")

    # Procesar con el CIO
    reply_text = process_whatsapp_message(incoming_text, sender)

    # Si la petición provino de Twilio, responder con TwiML
    if "twilio" in request.headers.get("user-agent", "").lower() or "application/x-www-form-urlencoded" in content_type:
        twiml = generate_twiml_response(reply_text)
        return Response(content=twiml, media_type="application/xml")

    # Respuesta JSON estándar
    return {
        "status": "success",
        "sender": sender,
        "query": incoming_text,
        "reply": reply_text
    }


@app.post("/api/whatsapp/simulate")
async def simulate_whatsapp_message(payload: ChatQueryRequest):
    """Permite probar exactamente cómo responderá el CIO en la pantalla de WhatsApp."""
    reply = process_whatsapp_message(payload.query)
    return {
        "incoming_query": payload.query,
        "whatsapp_preview": reply
    }

