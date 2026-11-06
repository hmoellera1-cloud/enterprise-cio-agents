"""
enterprise_agents.cli
Interfaz interactiva de línea de comandos para interactuar con el CIO, Ventas e Inventarios.
"""

from __future__ import annotations
import sys
import argparse
import json
from enterprise_agents.database import init_database
from enterprise_agents.agents.cio_orchestrator import CIOAgent
from enterprise_agents.agents.sales_agent import SalesAgent
from enterprise_agents.agents.inventory_agent import InventoryAgent


# Colores ANSI para terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"{CYAN}{BOLD}")
    print("=" * 72)
    print("   SISTEMA CORPORATIVO MULTI-AGENTE CTIN: CIO, VENTAS & INVENTARIOS")
    print("=" * 72)
    print(f"{RESET}")


def run_executive_report():
    cio = CIOAgent()
    print_banner()
    print(f"{BOLD}[Generando Informe Ejecutivo del CIO - CTIN...]{RESET}\n")
    briefing = cio.generate_executive_briefing()

    print(f"{GREEN}{BOLD}=== {briefing.title.upper()} ==={RESET}")
    print(f"Fecha de emisión: {briefing.generated_at}\n")

    print(f"{YELLOW}{BOLD}▶ RESUMEN EJECUTIVO:{RESET}")
    print(f"{briefing.executive_summary}\n")

    print(f"{CYAN}{BOLD}▶ PERSPECTIVA ESTRATÉGICA DEL CIO:{RESET}")
    print(f"{briefing.cio_perspective}\n")

    print(f"{GREEN}{BOLD}▶ KPIS CLAVE DE VENTAS (USD):{RESET}")
    for k, v in briefing.sales_kpis.items():
        if "revenue" in k or "value" in k:
            print(f"  • {k.replace('_', ' ').title()}: ${v:,}")
        else:
            print(f"  • {k.replace('_', ' ').title()}: {v}")
    print()

    print(f"{CYAN}{BOLD}▶ KPIS CLAVE DE INVENTARIO (USD):{RESET}")
    for k, v in briefing.inventory_kpis.items():
        if k == "warehouses":
            continue
        if "valuation" in k:
            print(f"  • {k.replace('_', ' ').title()}: ${v:,}")
        else:
            print(f"  • {k.replace('_', ' ').title()}: {v}")
    print()

    if briefing.cross_functional_alerts:
        print(f"{RED}{BOLD}▶ ALERTAS DE RIESGO CRUZADO (VENTAS vs INVENTARIOS) [Top {min(10, len(briefing.cross_functional_alerts))} de {len(briefing.cross_functional_alerts)}]:{RESET}")
        for i, alert in enumerate(briefing.cross_functional_alerts[:10], 1):
            color = RED if alert.severity == "CRITICAL" else YELLOW
            print(f"  {color}[{alert.severity}] {i}. {alert.title}{RESET}")
            print(f"     Descripción: {alert.description}")
            print(f"     Impacto Ventas: {alert.sales_impact}")
            print(f"     Impacto Inventario: {alert.inventory_impact}")
            print(f"     Acción recomendada: {alert.recommended_action}\n")

    print(f"{BOLD}▶ INICIATIVAS ESTRATÉGICAS PRIORITARIAS:{RESET}")
    for init in briefing.strategic_initiatives:
        print(f"  {init}")
    print("\n" + "=" * 72)


def run_scenario_simulation():
    cio = CIOAgent()
    print_banner()
    print(f"{BOLD}[Simulación de Viabilidad Operativa por el CIO - CTIN]{RESET}\n")
    requested = [
        {"sku": "SKU-LAP-PRO16", "quantity": 12},
        {"sku": "SKU-LAP-AIR14", "quantity": 15},
        {"sku": "SKU-SEC-FIREWALL", "quantity": 6}
    ]
    print("Propuesta de Venta Corporativa solicitada:")
    for it in requested:
        print(f"  • SKU: {it['sku']} | Cantidad solicitada: {it['quantity']}")
    print()

    sim = cio.simulate_deal_feasibility(requested, client_name="Cliente Corporativo")
    
    status_color = GREEN if sim["is_feasible_immediately"] else RED
    status_label = "FACTIBLE INMEDIATAMENTE" if sim["is_feasible_immediately"] else "REQUIERE REABASTECIMIENTO PREVIO"
    
    print(f"Resultado de Evaluación: {status_color}{BOLD}{status_label}{RESET}")
    print(f"Ingresos estimados: ${sim['total_deal_revenue']:,}")
    print(f"Margen bruto estimado: ${sim['estimated_gross_margin']:,} ({sim['margin_percentage']}%)")
    print(f"\n{YELLOW}{BOLD}Dictamen del CIO:{RESET} {sim['cio_recommendation']}\n")
    
    print(f"{BOLD}Detalle por SKU evaluado:{RESET}")
    for it in sim["items_evaluation"]:
        avail_color = GREEN if it["can_fulfill_immediately"] else RED
        print(f"  • {it['name']} ({it['sku']}):")
        print(f"      Solicitado: {it['quantity']} | Disponible en almacén: {avail_color}{it['available_in_stock']}{RESET} | Plazo de reposición: {it['lead_time_days']} días")



def interactive_terminal():
    cio = CIOAgent()
    print_banner()
    print("Modo Interactivo. Escribe tu consulta para el CIO o sus agentes subordinados.")
    print("Ejemplos:")
    print("  - ¿Cuál es el estado general del negocio?")
    print("  - ¿Cuáles son los productos más vendidos?")
    print("  - ¿Cuáles son las alertas críticas de almacén?")
    print("  - Simular viabilidad de venta")
    print("Escribe 'salir' para terminar.\n")

    while True:
        try:
            query = input(f"{BOLD}{CYAN}Directorio > {RESET}").strip()
            if not query:
                continue
            if query.lower() in ["salir", "exit", "quit"]:
                print("Finalizando sesión con el CIO.")
                break

            response = cio.handle_request(query)
            print(f"\n{GREEN}{BOLD}[Respuesta de {response.agent_name}]:{RESET}")
            print(f"{response.summary}\n")
            if response.recommendations:
                print(f"{YELLOW}Recomendaciones:{RESET}")
                for r in response.recommendations:
                    print(f"  • {r}")
            print("-" * 72 + "\n")
        except (KeyboardInterrupt, EOFError):
            print("\nSesión finalizada.")
            break


def main():
    init_database()
    parser = argparse.ArgumentParser(description="Sistema Corporativo Multi-Agente (CIO, Ventas e Inventario)")
    parser.add_argument("--report", action="store_true", help="Genera el informe ejecutivo consolidado del CIO")
    parser.add_argument("--simulate", action="store_true", help="Ejecuta la simulación de viabilidad de una venta")
    parser.add_argument("--interactive", action="store_true", help="Inicia sesión interactiva de diálogo con el CIO")
    parser.add_argument("--serve", action="store_true", help="Inicia el servidor API REST con Uvicorn")
    parser.add_argument("--port", type=int, default=8000, help="Puerto para el servidor API REST")

    args = parser.parse_args()

    if args.report:
        run_executive_report()
    elif args.simulate:
        run_scenario_simulation()
    elif args.serve:
        import uvicorn
        print_banner()
        print(f"Iniciando API REST en http://localhost:{args.port}...")
        uvicorn.run("enterprise_agents.api:app", host="0.0.0.0", port=args.port, reload=False)
    else:
        # Por defecto o con --interactive
        if args.interactive or len(sys.argv) == 1:
            run_executive_report()
            interactive_terminal()


if __name__ == "__main__":
    main()
