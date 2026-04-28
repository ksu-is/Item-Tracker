import time
import json
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from typing import List, Dict, Optional

CONFIG_FILE = "track_config.json"
STATE_FILE = "track_state.json"

# ---------------------------
# Notification helpers
# ---------------------------

def send_email(smtp_host: str, smtp_port: int, username: str, password: str,
               from_addr: str, to_addrs: List[str], subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(username, password)
        s.sendmail(from_addr, to_addrs, msg.as_string())

def send_telegram(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# ---------------------------
# Page check logic
# ---------------------------

def fetch_page(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> str:
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (compatible; ItemTracker/1.0; +https://example.com)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def check_in_stock_from_html(html: str, method: str, query: str, in_stock_text: Optional[str]) -> bool:
    # method: "css" or "text"
    soup = BeautifulSoup(html, "html.parser")
    if method == "css":
        el = soup.select_one(query)
        if el is None:
            # if selector missing, assume out of stock
            return False
        txt = el.get_text(separator=" ", strip=True).lower()
    else:
        txt = soup.get_text(separator=" ", strip=True).lower()
    if in_stock_text:
        return in_stock_text.lower() in txt
    # fallback simple heuristic: look for "out of stock"/"sold out"
    blocked = ["out of stock", "sold out", "unavailable", "temporarily unavailable"]
    return not any(b in txt for b in blocked)

# ---------------------------
# Config/state management
# ---------------------------

def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

# ---------------------------
# Main tracking loop
# ---------------------------

def check_item(item_cfg: Dict) -> bool:
    """
    item_cfg keys:
      - name: friendly name
      - url: product page
      - method: "css" or "text"
      - query: css selector (if method == "css") or ignored
      - in_stock_text: optional text indicating in-stock presence
      - headers: optional dict of headers
    """
    html = fetch_page(item_cfg["url"], headers=item_cfg.get("headers"))
    return check_in_stock_from_html(html, item_cfg.get("method", "css"),
                                    item_cfg.get("query", ""), item_cfg.get("in_stock_text"))

def run_loop(config_path=CONFIG_FILE, state_path=STATE_FILE):
    config = load_json(config_path, {})
    items: List[Dict] = config.get("items", [])
    notify_cfg = config.get("notify", {})
    interval = config.get("interval_seconds", 300)

    state = load_json(state_path, {})

    print(f"Starting tracker for {len(items)} item(s). Poll interval {interval} sec.")
    while True:
        for item in items:
            name = item.get("name", item["url"])
            try:
                is_in_stock = check_item(item)
            except Exception as e:
                print(f"[{name}] Error fetching/checking: {e}")
                continue

            last = state.get(item["url"], {}).get("in_stock")
            if last is None:
                # first time, just record
                state[item["url"]] = {"in_stock": is_in_stock, "last_checked": int(time.time())}
                print(f"[{name}] initial state: {'IN' if is_in_stock else 'OUT'}")
                continue

            if is_in_stock and not last:
                # newly restocked => notify
                msg = f"Item back in stock: {name}\n{item['url']}"
                print(f"[{name}] RESTOCKED -> notifying")
                if notify_cfg.get("email", {}).get("enabled"):
                    e = notify_cfg["email"]
                    try:
                        send_email(e["smtp_host"], e["smtp_port"], e["username"], e["password"],
                                   e["from_addr"], e["to_addrs"], f"[Restock] {name}", msg)
                    except Exception as ex:
                        print("Email send failed:", ex)
                if notify_cfg.get("telegram", {}).get("enabled"):
                    t = notify_cfg["telegram"]
                    try:
                        send_telegram(t["bot_token"], t["chat_id"], msg)
                    except Exception as ex:
                        print("Telegram send failed:", ex)

            state[item["url"]] = {"in_stock": is_in_stock, "last_checked": int(time.time())}
        save_json(state_path, state)
        time.sleep(interval)

if __name__ == "__main__":
    run_loop()
