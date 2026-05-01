import time
import schedule
from rich.console import Console

from core.scanner import run_scan
from core.report import generate_daily_report

def main_daemon():
    console = Console()
    console.print("[bold blue]🦊 Foxbit Trader Daemon is Starting...[/bold blue]")
    
    # Schedule the market scan every 1 hour
    schedule.every(1).hours.do(run_scan)
    console.print("✅ Market Scanner scheduled: [bold]Every 1 hour[/bold]")
    
    # Schedule the daily notification report at 10:00 AM
    schedule.every().day.at("10:00").do(generate_daily_report)
    console.print("✅ Daily Notification scheduled: [bold]10:00 AM[/bold]")
    
    console.print("\n[dim]The daemon is now running in the background. Press Ctrl+C to stop.[/dim]")
    
    # Run an initial scan immediately on startup
    console.print("\n[dim]Triggering initial startup scan...[/dim]")
    run_scan()
    
    while True:
        schedule.run_pending()
        time.sleep(60) # Wait one minute before checking schedule again

if __name__ == "__main__":
    try:
        main_daemon()
    except KeyboardInterrupt:
        print("\n🛑 Daemon stopped by user.")
