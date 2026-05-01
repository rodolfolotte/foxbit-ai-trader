import sys
import os
import json
import time
from datetime import datetime
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from rich.console import Console

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from core.foxbit_client import FoxbitClient
from core.strategies.confluence import evaluate_confluence

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

def get_entry_price(market: str) -> float:
    """
    Looks backwards through the trade history ledger to find the 
    price at which we most recently bought the held asset.
    """
    log_file = "data/trade_history.json"
    if not os.path.exists(log_file): 
        return 0.0
    try:
        with open(log_file, "r") as f:
            trades = json.load(f)
        for t in reversed(trades):
            if t['market'].upper() == market.upper() and t['action'] == "BUY" and t.get('status') in ["SUCCESS", "PAPER"]:
                return float(t['price'])
    except Exception:
        pass
    return 0.0

def log_trade(market: str, action: str, price: float, quantity: float, status: str, reason: str = ""):
    log_file = "data/trade_history.json"
    trades = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                trades = json.load(f)
        except json.JSONDecodeError:
            trades = []
            
    trade_record = {
        "timestamp": datetime.now().isoformat(),
        "market": market,
        "action": action,
        "price": price,
        "quantity": quantity,
        "status": status,
        "reason": reason
    }
    
    trades.append(trade_record)
    with open(log_file, "w") as f:
        json.dump(trades, f, indent=4)

def export_market_state(market_data: list):
    state_file = "data/market_state.json"
    with open(state_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "markets": market_data
        }, f, indent=4)

def get_macro_trend(client: FoxbitClient, market_symbol: str) -> str:
    try:
        data = client.get_candlesticks(market_symbol, interval="1d", limit=30)
        if not data or len(data) < 25:
            return "UNKNOWN"
            
        data.reverse()
        df = pd.DataFrame(data).iloc[:, :6]
        df.columns = ["timestamp", "open", "high", "low", "close", "close_time"]
        df["close"] = pd.to_numeric(df["close"])
        
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        
        latest = df.iloc[-1]
        
        ema_9_col = [c for c in df.columns if c.startswith('EMA_9')][0]
        ema_21_col = [c for c in df.columns if c.startswith('EMA_21')][0]
        ema_9 = latest[ema_9_col]
        ema_21 = latest[ema_21_col]
        
        if ema_9 > ema_21:
            return "BULL"
        elif ema_9 < ema_21:
            return "BEAR"
    except Exception:
        pass
    return "UNKNOWN"

def run_scan():
    console = Console()
    console.print(f"\n[bold magenta]== Foxbit Global Market Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==[/bold magenta]")
    
    # 1. Initialize Configuration
    load_dotenv()
    trade_amount_brl = float(os.getenv("TRADE_AMOUNT_BRL", "100"))
    app_status = os.getenv("APP_STATUS", "PAPER")
    strategy_mode = os.getenv("STRATEGY_MODE", "MAX_GAIN")
    
    if strategy_mode == "LONG_TERM":
        interval = "1h"
        take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "20.0"))
        stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "10.0"))
        console.print("[dim]Mode: [bold blue]LONG TERM[/bold blue] (1h candles, TP: 20%, SL: 10%)[/dim]")
    else:
        interval = "15m"
        take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))
        stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "3.0"))
        console.print("[dim]Mode: [bold magenta]MAX GAIN[/bold magenta] (15m candles, TP: 5%, SL: 3%)[/dim]")
        
    min_volume_brl = 50000.0  
    
    client = FoxbitClient()
    
    try:
        all_markets = client.get_markets().get("data", [])
        brl_markets = [m.get("symbol", "").lower() for m in all_markets if m.get("symbol", "").lower().endswith("brl")]
    except Exception as e:
        console.print(f"[bold red]Failed to fetch markets: {e}[/bold red]")
        return

    market_state_list = []
    immediate_sells = []
    
    best_buy = None
    best_buy_rsi = 100.0
    
    best_sell = None
    best_sell_rsi = 0.0
    
    held_coins = []
    try:
        accounts = client.get_balances().get("data", [])
        for account in accounts:
            symbol = account.get("currency_symbol", account.get("symbol", "")).lower()
            balance = float(account.get("balance", account.get("available", "0")))
            if balance > 0 and symbol != "brl":
                held_coins.append(f"{symbol}brl")
    except Exception:
        pass

    # 3. Scanning Loop
    for market in brl_markets:
        try:
            time.sleep(0.1)
            
            data = client.get_candlesticks(market, interval=interval, limit=100)
            if not data or len(data) < 96: continue
                
            try:
                volume_24h = sum(float(candle[7]) for candle in data[:96])
            except Exception:
                volume_24h = 0.0
                
            if volume_24h < min_volume_brl: continue
            
            # --- PnL Protection Logic ---
            data.reverse()
            df = pd.DataFrame(data).iloc[:, :6]
            df.columns = ["timestamp", "open", "high", "low", "close", "close_time"]
            for col in ["open", "high", "low", "close"]: df[col] = pd.to_numeric(df[col])
            
            current_price = df['close'].iloc[-1]
            skip_confluence = False
            
            if market in held_coins:
                entry_price = get_entry_price(market)
                if entry_price > 0:
                    pct_change = ((current_price - entry_price) / entry_price) * 100
                    
                    if pct_change >= take_profit_pct:
                        reason_str = f"✅ Take Profit Triggered (+{pct_change:.1f}%)"
                        immediate_sells.append({"market": market, "price": current_price, "reason": reason_str})
                        skip_confluence = True
                        
                    elif pct_change <= -stop_loss_pct:
                        reason_str = f"❌ Stop Loss Triggered ({pct_change:.1f}%)"
                        immediate_sells.append({"market": market, "price": current_price, "reason": reason_str})
                        skip_confluence = True
            
            if skip_confluence:
                continue
                
            # --- Confluence Logic ---
            macro_trend = get_macro_trend(client, market)
            result = evaluate_confluence(df, macro_trend=macro_trend)
            if "error" in result: continue
            
            vote_mbb = result['vote_macd_bb']
            vote_rsi = result['vote_rsi']
            vote_ema = result['vote_ema']
            decision = result['decision']
            
            market_state_list.append({
                "market": market.upper(),
                "macro": macro_trend,
                "macd_vote": "BUY" if vote_mbb == 1 else "SELL" if vote_mbb == -1 else "HOLD",
                "rsi_vote": "BUY" if vote_rsi == 1 else "SELL" if vote_rsi == -1 else "HOLD",
                "ema_vote": "BUY" if vote_ema == 1 else "SELL" if vote_ema == -1 else "HOLD",
                "decision": decision
            })
            
            current_rsi = df.iloc[-1][[c for c in df.columns if c.startswith('RSI')][0]]
            reason_str = f"Macro: {macro_trend} | MACD: {vote_mbb} | RSI: {vote_rsi} ({current_rsi:.1f}) | EMA: {vote_ema}"
            
            if decision == "BUY" and current_rsi < best_buy_rsi:
                best_buy = {"market": market, "price": current_price, "rsi": current_rsi, "reason": reason_str}
                best_buy_rsi = current_rsi
                    
            if decision == "SELL" and market in held_coins and current_rsi > best_sell_rsi:
                best_sell = {"market": market, "price": current_price, "rsi": current_rsi, "reason": reason_str}
                best_sell_rsi = current_rsi
                    
        except Exception:
            pass

    export_market_state(market_state_list)
    
    # 4. Execution Logic
    all_sells = immediate_sells + ([best_sell] if best_sell else [])
    
    for sell_target in all_sells:
        mkt = sell_target['market'].upper()
        price = sell_target['price']
        reason = sell_target['reason']
        qty = round(trade_amount_brl / price, 8)
        
        console.print(f"\n🚀 [bold red]EXECUTING SELL: {mkt}[/bold red] - {reason}")
        
        if app_status == "LIVE":
            try:
                # client.create_order(mkt.lower(), side="SELL", order_type="MARKET", quantity=str(qty))
                log_trade(mkt, "SELL", price, qty, "SUCCESS", reason)
            except Exception as e:
                log_trade(mkt, "SELL", price, qty, "ERROR", reason)
        else:
            log_trade(mkt, "SELL", price, qty, "PAPER", reason)

    if best_buy:
        mkt = best_buy['market'].upper()
        price = best_buy['price']
        reason = best_buy['reason']
        qty = round(trade_amount_brl / price, 8)
        
        console.print(f"\n🛒 [bold green]EXECUTING BUY: {mkt}[/bold green] - {reason}")
        
        if app_status == "LIVE":
            try:
                # client.create_order(mkt.lower(), side="BUY", order_type="MARKET", quantity=str(qty))
                log_trade(mkt, "BUY", price, qty, "SUCCESS", reason)
            except Exception as e:
                log_trade(mkt, "BUY", price, qty, "ERROR", reason)
        else:
            log_trade(mkt, "BUY", price, qty, "PAPER", reason)

if __name__ == "__main__":
    run_scan()
