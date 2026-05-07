import requests
from bs4 import BeautifulSoup
import time
import json
import os

# --- CONFIGURATION ---
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1501733422685618287/d0G2YKxq5S4M4T8Y79FmGZQqudiapkS4ZP-Z6Sv6EwfcWofdBA_m4DlY2CQa87Iii15I"

# Items you want to track
# Update the URLs and 'in_stock_text' based on the specific store
TRACKING_LIST = [
    {
        "name": "NeeDoh FuzzBall",
        "url": "https://www.amazon.com/Schylling-NeeDoh-Fuzz-Ball-Sensory/dp/B0DR3H6G51/ref=sr_1_1?crid=3TSJLTEAWE59C&dib=eyJ2IjoiMSJ9.STWgLSnkBCsCO9xANjFW7OMkq84DWylVj9WthJPFlOrBrrD6Ivud8gozwDW2uAQxBE0IuFdr6mYWK76dA804WRtaWDglfcHnKIxowbSB9mDSWdDFT0HzdrxvvajhicpAKGCI0EgF5JIFLgY1K1L18wKw4OokFPuYFF5RtO9HF9g1aZNLWgQ7GR5BVFPtUFE6zly8HeE8zDlepvseZQl4qWKCqMDnsSB15NAzMpWtU5s6ixHHNUIUxsmQgaxRERh9-zO7M-vT1QzSchmK_ClodwDPqmvQUlkjyKR0nnEmt7U.MWQlx2ZWG1oV4W7IwwC6J5KlQLZ9Tip88andCPPq13w&dib_tag=se&keywords=needoh&qid=1778113355&sprefix=needoh+%2Caps%2C202&sr=8-1",
        "in_stock_text": "Add to Cart" 
    }
]

LOG_FILE = "tracker_log.txt"
CHECK_INTERVAL = 300  # Check every 5 minutes (300 seconds)

# --- FUNCTIONS ---

def send_discord_notification(message):
    """Sends a message to your Discord channel."""
    data = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"Discord alert failed: {e}")

def check_stock(url, search_text):
    """Scrapes the page to see if the 'In Stock' text exists."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # If the search text (like 'Add to Cart') is found, return True
        return search_text.lower() in soup.get_text().lower()
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return False

def log_event(message):
    """Saves a timestamped message to a local text file."""
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: {message}\n")

# --- MAIN LOOP ---

def main():
    print(f"🚀 NeeDoh Navigator Started. Tracking {len(TRACKING_LIST)} items.")
    
    # Track the last known status to avoid spamming notifications
    last_status = {item['url']: False for item in TRACKING_LIST}

    while True:
        for item in TRACKING_LIST:
            name = item['name']
            url = item['url']
            search_text = item['in_stock_text']

            print(f"Checking {name}...")
            currently_in_stock = check_stock(url, search_text)

            # Logic: If it WAS out of stock and is NOW in stock, notify!
            if currently_in_stock and not last_status[url]:
                msg = f"🚨 **RESTOCK ALERT**: {name} is back! \n🔗 Buy here: {url}"
                print(msg)
                send_discord_notification(msg)
                log_event(f"SUCCESS: {name} Restocked.")
            
            elif not currently_in_stock:
                print(f"{name} is still out of stock.")
            
            # Update the status for the next loop
            last_status[url] = currently_in_stock

        print(f"Waiting {CHECK_INTERVAL} seconds for next check...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
