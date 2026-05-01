#!/usr/bin/env python3
import os

def toggle_live_trading():
    env_file = ".env"
    live_status = False
    
    # Read current content
    content = ""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
            
    lines = content.split('\n')
    new_lines = []
    found = False
    
    for line in lines:
        if line.startswith("APP_STATUS="):
            found = True
            if "LIVE" in line:
                new_lines.append("APP_STATUS=PAPER")
                print("🛑 Live Trading is now OFF (PAPER MODE).")
            else:
                new_lines.append("APP_STATUS=LIVE")
                print("🟢 Live Trading is now ON (LIVE MODE).")
                live_status = True
        else:
            if line.strip():
                new_lines.append(line)
                
    if not found:
        new_lines.append("APP_STATUS=LIVE")
        print("🟢 Live Trading is now ON (LIVE MODE).")
        live_status = True
        
    with open(env_file, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')
        
    if live_status:
        print("WARNING: The bot will execute real API orders with your capital.")

if __name__ == "__main__":
    toggle_live_trading()
