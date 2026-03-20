from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import time
import random
from datetime import datetime



DATABASE_URL = os.getenv("DATABASE_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BESTSELLER_URLS = [
    "https://www.amazon.in/gp/bestsellers/electronics/",
    "https://www.amazon.in/gp/bestsellers/computers/",
    "https://www.amazon.in/gp/bestsellers/mobile/",
    "https://www.amazon.in/gp/bestsellers/appliances/",
    "https://www.amazon.in/gp/bestsellers/sports/",
]

def get_db():
    return psycopg2.connect(DATABASE_URL)

def get_bestseller_asins(category_url):
    try:
        time.sleep(random.uniform(2, 4))
        res = requests.get(category_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        asins = []
        items = soup.find_all("div", {"data-asin": True})
        for item in items:
            asin = item.get("data-asin")
            if asin and len(asin) == 10:
                asins.append(asin)
        
        print(f"Found {len(asins)} products in {category_url}")
        return asins[:50]
    except Exception as e:
        print(f"Error getting bestsellers: {e}")
        return []

def scrape_product_price(asin):
    try:
        url = f"https://www.amazon.in/dp/{asin}"
        time.sleep(random.uniform(3, 6))
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")

        price_elem = soup.find("span", {"class": "a-price-whole"})
        title_elem = soup.find("span", {"id": "productTitle"})

        if not price_elem:
            return None

        price_text = price_elem.get_text()
        cleaned = price_text.replace("₹","").replace(",","").replace(".","").strip()
        price = float(cleaned[:7])

        title = title_elem.get_text().strip()[:80] if title_elem else "Unknown"

        if price > 0:
            return {
                "asin": asin,
                "url": url,
                "title": title,
                "price": price
            }
        return None

    except Exception as e:
        print(f"Error scraping {asin}: {e}")
        return None

def save_price(url, title, price):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_history (url, title, price) VALUES (%s, %s, %s)",
            (url, title, price)
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"Saved: {title[:40]} — Rs.{price}")
    except Exception as e:
        print(f"DB error: {e}")

def collect_all_prices():
    print(f"Starting collection at {datetime.now()}")
    
    all_asins = []
    for url in BESTSELLER_URLS:
        asins = get_bestseller_asins(url)
        all_asins.extend(asins)
        time.sleep(2)

    # Remove duplicates
    all_asins = list(set(all_asins))
    print(f"Total unique products to track: {len(all_asins)}")

    success = 0
    for asin in all_asins:
        data = scrape_product_price(asin)
        if data:
            save_price(data["url"], data["title"], data["price"])
            success += 1
        time.sleep(random.uniform(2, 5))

    print(f"Collection complete. Saved {success}/{len(all_asins)} prices")

if __name__ == "__main__":
    collect_all_prices()

from apscheduler.schedulers.blocking import BlockingScheduler

if __name__ == "__main__":
    # Run once immediately
    collect_all_prices()
    
    # Then run every 6 hours
    scheduler = BlockingScheduler()
    scheduler.add_job(collect_all_prices, 'interval', hours=6)
    print("Scheduler started — collecting every 6 hours")
    scheduler.start()