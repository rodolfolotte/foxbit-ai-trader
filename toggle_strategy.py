import os

def toggle_strategy():
    env_file = ".env"
    
    # Defaults
    content = ""
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            content = f.read()

    lines = content.split('\n')
    new_lines = []
    found = False
    new_status = "MAX_GAIN"

    for line in lines:
        if line.startswith("STRATEGY_MODE="):
            found = True
            current = line.split("=")[1].strip()
            if current == "MAX_GAIN":
                new_status = "LONG_TERM"
                new_lines.append(f"STRATEGY_MODE={new_status}")
            else:
                new_status = "MAX_GAIN"
                new_lines.append(f"STRATEGY_MODE={new_status}")
        else:
            if line.strip() != "" or line == lines[-1]: # preserve some spacing but clean trailing
                new_lines.append(line)

    if not found:
        new_lines.append(f"STRATEGY_MODE={new_status}")

    with open(env_file, "w") as f:
        f.write('\n'.join(new_lines))

    print(f"🔄 Strategy Profile is now: {new_status}")

if __name__ == "__main__":
    toggle_strategy()
