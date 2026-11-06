"""
enterprise_agents
Sistema Multi-Agente Empresarial: Director de Información (CIO), Ventas e Inventarios.
"""

from enterprise_agents.agents.cio_orchestrator import CIOAgent
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent
from enterprise_agents.database import init_database

__version__ = "0.1.0"
__all__ = ["CIOAgent", "SalesAgent", "InventoryAgent", "init_database"]
