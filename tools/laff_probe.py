"""Probe TTR's Local API (companion app support): how soon laff changes show up.

    PYTHONPATH=src .venv/Scripts/python.exe tools/laff_probe.py

Turn on Companion App Support in TTR's Options and log in to a toon. The first request
of a session can take several seconds (TTR may ask in game whether to allow "Toontown
Controller Module": approve it); after that requests take a few milliseconds. Prints
your toon's info once and every laff change with the time it was seen, polling every
0.1 s. Get hit, and compare when the laff meter moved to when the line printed.
Ctrl+C stops it.
"""

import http.client
import json
import secrets
import sys
import time

from ttcontroller.config import CONFIG_DIR

PORTS = range(1547, 1553)  # 1547 for the first TTR, one more per extra toon
AGENT = "Toontown Controller Module"
TOKEN_FILE = CONFIG_DIR / "ttr_api_token"


def load_token() -> str:
    """TTR asks for consent once per Authorization value: keep one, saved, so it asks once."""
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    except OSError:
        pass
    token = secrets.token_hex(16)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


TOKEN = load_token()


def get(port: int, path: str, timeout: float = 2.0):
    # 127.0.0.1, not "localhost": resolving localhost can try a dead address first.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path, headers={
            "Host": f"localhost:{port}", "User-Agent": AGENT, "Authorization": TOKEN})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} {response.reason}: {body[:200]!r}")
        return json.loads(body.decode("utf-8"))
    finally:
        connection.close()


def find_ports() -> list[int]:
    found = []
    for port in PORTS:
        started = time.perf_counter()
        try:
            # Long timeout: the first request may wait while the consent prompt shows.
            get(port, "/toon.json", timeout=60)
        except ConnectionRefusedError:
            continue  # no TTR on this port
        except Exception as error:
            print(f"Port {port}: {type(error).__name__}: {error}")
            continue
        print(f"Port {port}: answered (first request {time.perf_counter() - started:.1f} s)")
        found.append(port)
    return found


def flash_window(port: int) -> None:
    """A small always-on-top square: red on a hit, green on a heal. Drag it next to
    the laff meter and compare the two. It never takes focus from TTR."""
    import ctypes
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    size = 90
    root.geometry(f"{size}x{size}+20+{root.winfo_screenheight() - size - 260}")
    label = tk.Label(root, text="laff\n…", font=("Segoe UI", 14, "bold"), bg="#333", fg="white")
    label.pack(fill="both", expand=True)
    root.update_idletasks()
    # No activation: clicking or flashing it leaves TTR focused.
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                          user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    drag = {}
    label.bind("<ButtonPress-1>", lambda e: drag.update(x=e.x, y=e.y))
    label.bind("<B1-Motion>", lambda e: root.geometry(
        f"+{root.winfo_x() + e.x - drag['x']}+{root.winfo_y() + e.y - drag['y']}"))
    label.bind("<Button-3>", lambda e: root.destroy())  # right-click closes it

    state = {"last": None, "reset": None}

    def poll():
        try:
            laff = get(port, "/laff.json")
            value = laff.get("current")
        except Exception as error:
            print(f"{time.strftime('%H:%M:%S')} {type(error).__name__}: {error}", flush=True)
            value = None
        last = state["last"]
        if value is not None:
            if last is not None and value != last:
                stamp = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
                print(f"{stamp} laff {value}/{laff.get('max')} ({value - last:+d})", flush=True)
                label.config(bg="#e02020" if value < last else "#20b040")
                if state["reset"]:
                    root.after_cancel(state["reset"])
                state["reset"] = root.after(400, lambda: label.config(bg="#333"))
            label.config(text=f"laff\n{value}")
            state["last"] = value
        root.after(50, poll)

    poll()
    print("Flash square is up (bottom-left). Drag it beside the laff meter; right-click closes it.", flush=True)
    root.mainloop()


def main() -> None:
    if "--flash" in sys.argv:
        ports = find_ports()
        if not ports:
            sys.exit("No TTR answered. Is Companion App Support on, and are you logged in to a toon?")
        flash_window(ports[0])
        return
    print("Looking for TTR on ports 1547-1552 (approve the prompt in game if it shows)...", flush=True)
    ports = find_ports()
    if not ports:
        sys.exit("No TTR answered. Is Companion App Support on, and are you logged in to a toon?")
    for port in ports:
        print(f"\nPort {port}:")
        print(json.dumps(get(port, "/info.json"), indent=2)[:3000])
    print("\nWatching laff (Ctrl+C stops)...", flush=True)
    last = {}
    start = time.perf_counter()
    slowest = 0.0
    try:
        while True:
            for port in ports:
                asked = time.perf_counter()
                try:
                    laff = get(port, "/laff.json")
                except Exception as error:
                    print(f"{time.strftime('%H:%M:%S')} port {port}: {type(error).__name__}: {error}", flush=True)
                    continue
                took = time.perf_counter() - asked
                slowest = max(slowest, took)
                value = (laff.get("current"), laff.get("max"))
                if last.get(port) != value:
                    change = "" if port not in last else f" ({value[0] - last[port][0]:+d})"
                    stamp = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
                    print(f"{stamp} port {port}: laff {value[0]}/{value[1]}{change}"
                          f"  [request {took * 1000:.0f} ms]", flush=True)
                    last[port] = value
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\nRan {time.perf_counter() - start:.0f} s; slowest request {slowest * 1000:.0f} ms.")


if __name__ == "__main__":
    main()
