import os
import time
import re
import json
import random
import requests
import shutil
from datetime import datetime
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from playwright.sync_api import sync_playwright
from collections import Counter

# ---------------- CONFIG ----------------
BASE_URL = "https://www.ajio.com"
SOURCE_PLATFORM = "Ajio"
OUT_PREFIX = "ajio"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = os.path.join(os.getcwd(), f"{OUT_PREFIX}_scrape_{TIMESTAMP}")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
CSV_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.csv")
JSON_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.json")

SCROLL_PAUSE_TIME = 1.5
MAX_SCROLL_TRIES = 80
NO_GROWTH_CYCLES = 5
DOWNLOAD_IMAGES = True  # set True to download all images

console = Console()
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# ---------------- KEYWORDS ----------------
CATEGORIES = {
    "Shoes": {
        "Women": [
            "women+high+heels+designer",
            "women+sneakers+athletic",
            "women+boots+ankle",
            "women+sandals+summer",
            "women+loafers+formal",
            "women+wedges+casual",
            "women+flats+ballet",
            "women+platform+shoes",
            "women+espadrilles"
        ]
    }
}

# ---------------- UTILITIES ----------------
def clean_text(text):
    return re.sub(r'\s+', ' ', text.strip()) if text else ""

def extract_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else None
    except:
        return None

def download_image(image_url, folder_path, filename):
    if not image_url: 
        return None
    os.makedirs(folder_path, exist_ok=True)
    local_path = os.path.join(folder_path, filename)
    if os.path.exists(local_path): 
        return local_path
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(image_url, headers=headers, stream=True, timeout=20)
        if resp.status_code == 200:
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(resp.raw, f)
            return local_path
    except:
        return None
    return None

def parse_product(el, category="Shoes", gender="Women"):
    pdata = {
        "product_id": "",
        "category": category,
        "gender": gender,
        "product_url": "",
        "product_name": "",
        "brand": "",
        "price": None,
        "original_price": None,
        "discount_percent": "",
        "rating": "",
        "reviews": "",
        "price_tier": "",
        "image_url": "",
        "image_unique_name": "",
        "source_platform": SOURCE_PLATFORM
    }
    try:
        href = el.get("href") or ""
        if href:
            pdata["product_url"] = BASE_URL + href
            if "/p/" in href:
                pdata["product_id"] = href.split("/p/")[-1].split("?")[0]

        pdata["product_name"] = clean_text(el.get("name"))
        pdata["brand"] = clean_text(el.get("brand"))
        pdata["price"] = extract_price(el.get("price"))
        pdata["original_price"] = extract_price(el.get("original_price"))
        pdata["discount_percent"] = clean_text(el.get("discount"))
        pdata["rating"] = clean_text(el.get("rating"))
        pdata["reviews"] = clean_text(el.get("reviews"))

        img = el.get("image") or el.get("image_fallback")
        pdata["image_url"] = img if img and img.startswith("http") else ""

        if pdata["product_id"]:
            base_name = re.sub(r'[^a-zA-Z0-9]+', '-', pdata["product_name"].lower())[:50]
            brand_name = re.sub(r'[^a-zA-Z0-9]+', '-', pdata["brand"].lower())[:20]
            pdata["image_unique_name"] = f"{pdata['product_id']}-{brand_name}-{base_name}.jpg"

        p = pdata["price"]
        if p is None:
            pdata["price_tier"] = "unknown"
        elif p < 3000:
            pdata["price_tier"] = "affordable"
        elif p < 8000:
            pdata["price_tier"] = "mid"
        else:
            pdata["price_tier"] = "expensive"

    except:
        pass

    return pdata

# ---------------- SCRAPER ----------------
def scrape_ajio_keywords():
    all_products = []
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for category, genders in CATEGORIES.items():
            for gender, keywords in genders.items():
                for keyword in keywords:
                    search_url = f"https://www.ajio.com/s/{keyword}?query=:relevance"
                    console.print(Panel(f"[bold green]Scraping keyword:[/bold green] {keyword}"))
                    page.goto(search_url, timeout=60000)
                    page.wait_for_selector("div.rilrtl-products-list__item", timeout=30000)

                    # Infinite scroll
                    prev_count, stable_cycles, tries = 0, 0, 0
                    while tries < MAX_SCROLL_TRIES and stable_cycles < NO_GROWTH_CYCLES:
                        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        time.sleep(SCROLL_PAUSE_TIME + random.random())
                        items = page.query_selector_all("div.rilrtl-products-list__item")
                        curr_count = len(items)
                        if curr_count == prev_count:
                            stable_cycles += 1
                        else:
                            stable_cycles = 0
                        prev_count = curr_count
                        tries += 1

                    # Extract data
                    for item in page.query_selector_all("div.rilrtl-products-list__item"):
                        el_data = {}
                        try: el_data["href"] = item.query_selector("a.rilrtl-products-list__link.desktop").get_attribute("href")
                        except: el_data["href"] = ""
                        try: el_data["name"] = item.query_selector("div.nameCls").inner_text()
                        except: el_data["name"] = ""
                        try: el_data["brand"] = item.query_selector("div.brand strong").inner_text()
                        except: el_data["brand"] = ""
                        try: el_data["price"] = item.query_selector("span.price strong").inner_text()
                        except: el_data["price"] = None
                        try: el_data["original_price"] = item.query_selector("span.orginal-price").inner_text()
                        except: el_data["original_price"] = None
                        try: el_data["discount"] = item.query_selector("span.discount").inner_text()
                        except: el_data["discount"] = ""
                        try: el_data["rating"] = item.query_selector("p._3I65V").inner_text()
                        except: el_data["rating"] = ""
                        try: el_data["reviews"] = item.query_selector("div._2mae- p[aria-label*='reviews']").inner_text()
                        except: el_data["reviews"] = ""
                        try:
                            img_el = item.query_selector("img.rilrtl-lazy-img")
                            el_data["image"] = img_el.get_attribute("src") if img_el else None
                            if not el_data["image"]:
                                el_data["image_fallback"] = img_el.get_attribute("data-src") if img_el else None
                        except:
                            el_data["image"] = None

                        pdata = parse_product(el_data, category, gender)

                        if DOWNLOAD_IMAGES and pdata["image_url"]:
                            folder_path = os.path.join(IMAGES_DIR, category, gender)
                            _ = download_image(pdata["image_url"], folder_path, pdata["image_unique_name"])

                        all_products.append(pdata)

        browser.close()

    # Save outputs
    df = pd.DataFrame(all_products)
    df.to_csv(CSV_FILENAME, index=False)
    with open(JSON_FILENAME, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    products_count = len(all_products)
    products_per_min = round(products_count / (elapsed / 60), 2) if elapsed > 0 else 0

    # Summary
    brand_counts = Counter([p["brand"] for p in all_products if p["brand"]])
    top_brands = brand_counts.most_common(10)

    console.print(Panel("[bold blue]Final Scraping Summary[/bold blue]"))
    console.print(f"Total Products Scraped: {products_count}")
    console.print(f"Total Time: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
    console.print(f"Products/Minute: {products_per_min}")
    console.print(f"CSV File: {CSV_FILENAME}")
    console.print(f"JSON File: {JSON_FILENAME}")
    console.print("\n[bold green]Top Brands:[/bold green]")
    for b, c in top_brands:
        console.print(f"{b}: {c}")

if __name__ == "__main__":
    scrape_ajio_keywords()
