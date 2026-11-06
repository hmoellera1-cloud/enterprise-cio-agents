"""
enterprise_agents.models
Modelos de datos para comunicación e intercambio estructurado de información entre agentes.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    sender: str
    recipient: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class AgentResponse(BaseModel):
    agent_name: str
    status: str = "success"
    summary: str
    details: Optional[Dict[str, Any]] = None
    recommendations: List[str] = Field(default_factory=list)


class TopProductMetric(BaseModel):
    sku: str
    name: str
    category: str
    total_units_sold: int
    total_revenue: float
    current_stock: int
    stock_status: str


class SalesOverview(BaseModel):
    total_revenue: float
    total_orders: int
    completed_orders: int
    pending_orders: int
    average_order_value: float
    top_products: List[TopProductMetric]
    sales_by_region: Dict[str, float]


class CriticalStockItem(BaseModel):
    sku: str
    product_name: str
    category: str
    quantity_on_hand: int
    quantity_reserved: int
    available_stock: int
    min_safety_stock: int
    reorder_point: int
    lead_time_days: int
    urgency_level: str


class InventoryOverview(BaseModel):
    total_skus: int
    total_units_in_stock: int
    total_inventory_valuation: float
    critical_items_count: int
    critical_items: List[CriticalStockItem]
    warehouses_summary: List[Dict[str, Any]]


class CrossAgentAlert(BaseModel):
    severity: str  # CRITICAL, WARNING, INFO
    title: str
    description: str
    sales_impact: str
    inventory_impact: str
    recommended_action: str


class ExecutiveBriefing(BaseModel):
    title: str
    generated_at: str
    executive_summary: str
    cio_perspective: str
    sales_kpis: Dict[str, Any]
    inventory_kpis: Dict[str, Any]
    cross_functional_alerts: List[CrossAgentAlert]
    strategic_initiatives: List[str]
