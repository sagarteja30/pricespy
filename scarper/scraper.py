import random
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from backend.logging_config import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


def scrape_amazon_price(url: str) -> dict | None:
    try:
        time.sleep(random.uniform(2, 5))
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        price_elem = (
            soup.find("span", {"class": "a-price-whole"}) or
            soup.find("span", {"id": "priceblock_ourprice"}) or
            soup.find("span", {"class": "a-offscreen"})
        )

        title_elem = soup.find("span", {"id": "productTitle"})

        if not price_elem:
            logger.warning(f"No price element found for {url}")
            return None

        price_text = price_elem.get_text()
        price = float(
            price_text.replace("₹", "")
                      .replace(",", "")
                      .replace(".", "")
                      .strip()
        )

        return {
            "url": url,
            "title": title_elem.get_text().strip() if title_elem else "Unknown",
            "price": price,
            "scraped_at": datetime.utcnow(),
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error scraping {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Scraping error for {url}: {e}")
        return None


def save_price(data: dict, conn) -> bool:
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO price_history (url, title, price, scraped_at)
            VALUES (%s, %s, %s, %s)
            """,
            (data["url"], data["title"], data["price"], data["scraped_at"]),
        )
        conn.commit()
        cur.close()
        logger.debug(f"Saved price for {data['title'][:40]}: Rs.{data['price']}")
        return True
    except Exception as e:
        logger.error(f"Failed to save price: {e}")
        return False
