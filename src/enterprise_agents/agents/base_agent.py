"""
enterprise_agents.agents.base_agent
Clase base para todos los agentes del ecosistema empresarial.
"""

from __future__ import annotations
import inspect
import json
from typing import Any, Callable, Dict, List, Optional
import datetime
from enterprise_agents.models import AgentMessage, AgentResponse


class BaseAgent:
    def __init__(self, name: str, role: str, description: str, system_prompt: str):
        self.name = name
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.tools: Dict[str, Callable] = {}
        self.history: List[AgentMessage] = []

    def register_tool(self, func: Callable, name: Optional[str] = None) -> None:
        """Registra una función como herramienta accesible para el agente."""
        tool_name = name or func.__name__
        self.tools[tool_name] = func

    def list_tools(self) -> List[Dict[str, str]]:
        """Devuelve un catálogo de herramientas registradas con su documentación."""
        catalog = []
        for name, func in self.tools.items():
            catalog.append({
                "name": name,
                "doc": inspect.getdoc(func) or "Sin descripción"
            })
        return catalog

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Ejecuta una herramienta de manera controlada y segura."""
        if tool_name not in self.tools:
            raise ValueError(f"Herramienta '{tool_name}' no encontrada en {self.name}.")
        return self.tools[tool_name](**kwargs)

    def log_message(self, sender: str, recipient: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> AgentMessage:
        msg = AgentMessage(
            sender=sender,
            recipient=recipient,
            content=content,
            metadata=metadata,
            timestamp=datetime.datetime.now().isoformat()
        )
        self.history.append(msg)
        return msg

    def handle_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Método abstracto/virtual que cada agente implementa según su especialidad."""
        raise NotImplementedError("Cada agente debe implementar su propio handle_request.")
