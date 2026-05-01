import os
import json
from datetime import datetime, timedelta

def generate_daily_report():
    """
    Reads the trade_history.json for the last 24 hours,
    calculates metrics, and triggers a Linux notify-send alert.
    """
    log_file = "data/trade_history.json"
    
    if not os.path.exists(log_file):
        os.system("notify-send 'Foxbit Trader Report' 'No trade history found.'")
        return
        
    try:
        with open(log_file, "r") as f:
            trades = json.load(f)
    except json.JSONDecodeError:
        trades = []
        
    yesterday = datetime.now() - timedelta(hours=24)
    
    recent_trades = []
    for t in trades:
        try:
            t_time = datetime.fromisoformat(t["timestamp"])
            if t_time >= yesterday:
                recent_trades.append(t)
        except Exception:
            pass
            
    total_buys = sum(1 for t in recent_trades if t["action"] == "BUY")
    total_sells = sum(1 for t in recent_trades if t["action"] == "SELL")
    
    # Simple estimate: amount spent vs amount gained
    brl_spent = sum(t["price"] * t["quantity"] for t in recent_trades if t["action"] == "BUY")
    brl_gained = sum(t["price"] * t["quantity"] for t in recent_trades if t["action"] == "SELL")
    
    profit_estimate = brl_gained - brl_spent
    
    status_str = f"Estimated Flow: R$ {profit_estimate:.2f}"
    
    # Body message
    message = (
        f"Past 24h Summary:\n"
        f"• Trades Executed: {len(recent_trades)}\n"
        f"• Buys: {total_buys} | Sells: {total_sells}\n"
        f"• {status_str}\n"
        f"Check terminal for today's market conditions!"
    )
    
    # Fire notification
    # Using specific icon if wanted, but standard is fine
    os.system(f"notify-send -t 10000 'Foxbit Daily Report 🦊' '{message}'")
    print(f"[{datetime.now().isoformat()}] Sent Daily Report Notification.")

if __name__ == "__main__":
    generate_daily_report()
