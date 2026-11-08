"""
enterprise_agents.whatsapp_service
Módulo para integración bidireccional entre WhatsApp y el Director de Información (CIO).
Compatible con la API de Twilio WhatsApp Sandbox y Meta WhatsApp Cloud API.
"""

from __future__ import annotations
import urllib.parse
from typing import Dict, Any, Tuple
from enterprise_agents.agents.cio_orchestrator import CIOAgent

cio_agent = CIOAgent()


def format_whatsapp_response(raw_text: str, recommendations: list = None) -> str:
    """Da formato amigable con negritas y emojis optimizados para la pantalla de WhatsApp."""
    clean_text = raw_text.replace("€", "$")
    formatted = f"👔 *Director de Información (CIO - CTIN)*\n\n{clean_text}"
    formatted += "\n\n_— Sistema Multi-Agente Empresarial CTIN_"
    return formatted



def process_whatsapp_message(body_text: str, sender_number: str = "") -> str:
    """Procesa el mensaje recibido por WhatsApp, lo envía al CIO y genera la respuesta formateada."""
    query = body_text.strip()
    if not query:
        return "Por favor, escribe tu consulta para el CIO."

    # Interacción con el agente principal (CIO)
    response = cio_agent.handle_request(query)
    
    # Formatear para WhatsApp
    return format_whatsapp_response(response.summary, response.recommendations)


def generate_twiml_response(message_body: str) -> str:
    """Genera una respuesta XML TwiML estándar para Twilio WhatsApp."""
    # Escapar caracteres XML básicos
    escaped = (
        message_body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped}</Message>
</Response>"""
