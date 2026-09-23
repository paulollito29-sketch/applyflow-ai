import sys
import os
import yaml
from rich.console import Console
from rich.table import Table

from src.bot import LinkedInEasyApplyBot
from src.tracker import ApplicationTracker

console = Console()

def load_config():
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        console.print(f"[bold red]No se encontró el archivo de configuración {config_path}[/bold red]")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def show_help():
    console.print("""
[bold cyan]🤖 ApplyFlow AI — Autonomous Career & Application Engine[/bold cyan]

[bold yellow]Available Commands:[/bold yellow]
  [green]python run.py web[/green]       - Launches the Minimalist Real-Time Dashboard UI (http://localhost:8000)
  [green]python run.py login[/green]     - Opens interactive browser to link your LinkedIn session
  [green]python run.py apply[/green]     - Runs a one-time automated application batch
  [green]python run.py stats[/green]     - Displays applied jobs metrics and exports CSV report
  [green]python run.py export[/green]    - Exports application history to CSV
""")

def main():
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()
    config = load_config()

    if command == "web":
        import uvicorn
        console.print("[bold green]✨ Launching ApplyFlow AI Minimalist Web Dashboard on http://127.0.0.1:8000[/bold green]")
        uvicorn.run("src.web.server:app", host="127.0.0.1", port=8000, reload=False)

    elif command == "login":
        bot = LinkedInEasyApplyBot(config)
        bot.interactive_login()

    elif command == "apply":
        bot = LinkedInEasyApplyBot(config)
        bot.run_daily_applications()

    elif command == "stats":
        tracker = ApplicationTracker(config.get("bot_settings", {}).get("database_path", "data/applications.db"))
        stats = tracker.get_stats()
        
        table = Table(title="📊 Estadísticas de Postulaciones Automáticas")
        table.add_column("Estado", justify="left", style="cyan", no_wrap=True)
        table.add_column("Cantidad", justify="right", style="green")

        for status, count in stats.items():
            table.add_row(status, str(count))

        console.print(table)
        csv_file = tracker.export_to_csv()
        console.print(f"[bold blue]Reporte exportado en:[/bold blue] {csv_file}")

    elif command == "export":
        tracker = ApplicationTracker(config.get("bot_settings", {}).get("database_path", "data/applications.db"))
        csv_file = tracker.export_to_csv()
        console.print(f"[bold green]✔ Postulaciones exportadas exitosamente a:[/bold green] {csv_file}")

    else:
        show_help()

if __name__ == "__main__":
    main()
