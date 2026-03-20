import os
import random
import time
import re
from datetime import datetime

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from backend.logging_config import get_logger

logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

BESTSELLER_URLS = [
    "https://www.amazon.in/gp/bestsellers/electronics/",
    "https://www.amazon.in/gp/bestsellers/computers/",
    "https://www.amazon.in/gp/bestsellers/mobile/",
    "https://www.amazon.in/gp/bestsellers/appliances/",
    "https://www.amazon.in/gp/bestsellers/sports/",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def get_db():
    return psycopg2.connect(DATABASE_URL)


def is_blocked(soup):
    if soup.find("div", {"id": "captchacharacters"}) or soup.find("form", {"action": "/errors/validatecaptcha"}):
        return True
    if "api-services-support@amazon.com" in soup.get_text():
        return True
    return False


def get_price_from_soup(soup):
    price_selectors = [
        ("span", {"class": "a-price-whole"}),
        ("span", {"id": "priceblock_dealprice"}),
        ("span", {"id": "priceblock_ourprice"}),
        ("span", {"class": "a-offscreen"}),
        ("div", {"class": "a-section", "data-a-color": "price"}),
        ("span", {"data-a-color": "price"}),
        ("div", {"id": "corePrice_feature_div"}),
        ("span", {"class": "priceToPay"}),
    ]
    
    for tag, attrs in price_selectors:
        elem = soup.find(tag, attrs)
        if elem:
            text = elem.get_text()
            numbers = re.findall(r'[\d,]+', text.replace('₹', '').replace(',', ''))
            if numbers:
                try:
                    price = float(numbers[0].replace(',', ''))
                    if 10 < price < 1000000:
                        return price
                except ValueError:
                    continue
    
    price_pattern = re.compile(r'₹\s*([\d,]+)')
    match = price_pattern.search(soup.get_text())
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            pass
    
    return None


def get_title_from_soup(soup):
    title_selectors = [
        ("span", {"id": "productTitle"}),
        ("h1", {"id": "title"}),
        ("span", {"class": "product-title-word-break"}),
    ]
    
    for tag, attrs in title_selectors:
        elem = soup.find(tag, attrs)
        if elem:
            return elem.get_text().strip()[:100]
    
    return "Unknown"


def get_bestseller_asins(category_url: str) -> list[str]:
    try:
        time.sleep(random.uniform(2, 4))
        res = requests.get(category_url, headers=get_headers(), timeout=20)
        soup = BeautifulSoup(res.content, "html.parser")

        asins = []
        items = soup.find_all("div", {"data-asin": True})
        for item in items:
            asin = item.get("data-asin")
            if asin and len(asin) == 10:
                asins.append(asin)

        logger.info(f"Found {len(asins)} products in {category_url}")
        return asins[:30]
    except Exception as e:
        logger.error(f"Error getting bestsellers from {category_url}: {e}")
        return []


def scrape_product_price(asin: str) -> dict | None:
    try:
        url = f"https://www.amazon.in/dp/{asin}"
        time.sleep(random.uniform(4, 8))
        
        session = requests.Session()
        res = session.get(url, headers=get_headers(), timeout=20)
        soup = BeautifulSoup(res.content, "html.parser")
        
        if is_blocked(soup):
            logger.warning(f"Blocked by CAPTCHA for ASIN {asin}")
            time.sleep(30)
            return None
        
        price = get_price_from_soup(soup)
        title = get_title_from_soup(soup)
        
        if not price or price <= 0:
            logger.warning(f"No price found for ASIN {asin}")
            return None
        
        logger.info(f"Scraped {asin}: Rs.{price}")
        
        return {
            "asin": asin,
            "url": url,
            "title": title,
            "price": price,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for ASIN {asin}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error scraping ASIN {asin}: {e}")
        return None


def save_price(url: str, title: str, price: float) -> bool:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_history (url, title, price) VALUES (%s, %s, %s)",
            (url, title, price),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Saved: {title[:40]} — Rs.{price}")
        return True
    except Exception as e:
        logger.error(f"DB error saving price: {e}")
        return False


def collect_all_prices(limit: int = 50) -> dict:
    logger.info(f"Starting collection at {datetime.now()}")

    all_asins = []
    for url in BESTSELLER_URLS:
        asins = get_bestseller_asins(url)
        all_asins.extend(asins)
        time.sleep(random.uniform(3, 5))

    all_asins = list(set(all_asins))[:limit]
    logger.info(f"Total products to track: {len(all_asins)}")

    success = 0
    for asin in all_asins:
        data = scrape_product_price(asin)
        if data:
            save_price(data["url"], data["title"], data["price"])
            success += 1
        time.sleep(random.uniform(3, 6))

    logger.info(f"Collection complete. Saved {success}/{len(all_asins)} prices")
    return {"success": success, "total": len(all_asins)}


if __name__ == "__main__":
    collect_all_prices()
