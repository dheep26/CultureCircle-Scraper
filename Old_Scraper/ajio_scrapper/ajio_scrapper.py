import os
import time
import re
import json
import random
import shutil
from datetime import datetime
import pandas as pd
from collections import Counter
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from playwright.sync_api import sync_playwright

# ---------------- CONFIG ----------------
HEADLESS = False  # Set True for background
SOURCE_PLATFORM = "Ajio"
OUT_PREFIX = "ajio"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = os.path.join(os.getcwd(), f"{OUT_PREFIX}_scrape_{TIMESTAMP}")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
CSV_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.csv")
JSON_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.json")
SCROLL_PAUSE_TIME = 2
MAX_SCROLL_TRIES = 80
NO_GROWTH_CYCLES = 5
DOWNLOAD_IMAGES = True

# ---------------- KEYWORDS ----------------
keywords_map = {
    "Shoes": {
        "Women": [
            "women+sneakers",
            "women+heels",
            "women+sandals",
            "women+boots"
        ],
        "Men": [
            "men+sneakers",
            "men+formal+shoes",
            "men+sandals",
            "men+slippers"
        ]
    }
}

console = Console()
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# ---------------- UTILITIES ----------------
def clean_text(text):
    return re.sub(r'\s+', ' ', text.strip()) if text else ""

def extract_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
    return float(cleaned) if cleaned else None

def generate_image_names(product_name, brand, category="Shoes", gender="Men"):
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', (product_name or "").lower())
    clean_name = re.sub(r'\s+', '-', clean_name)[:60]
    clean_brand = re.sub(r'[^a-zA-Z0-9\s]', '', (brand or "nobrand").lower())
    clean_brand = re.sub(r'\s+', '-', clean_brand)[:30]
    folder_path = os.path.join(IMAGES_DIR, category, gender)
    os.makedirs(folder_path, exist_ok=True)
    image_name = f"{clean_name}-{clean_brand}.jpg"
    relative_path = os.path.join("images", category, gender, image_name)
    return folder_path, image_name, relative_path

def download_image(playwright_page, image_url, folder_path, filename):
    """Download image using Playwright (avoids bot block)"""
    try:
        local_path = os.path.join(folder_path, filename)
        if os.path.exists(local_path):
            return local_path
        content = playwright_page.evaluate(
            """async (url) => {
                const response = await fetch(url);
                const buffer = await response.arrayBuffer();
                return Array.from(new Uint8Array(buffer));
            }""",
            image_url,
        )
        with open(local_path, "wb") as f:
            f.write(bytearray(content))
        return local_path
    except:
        return None

def parse_product(el, category="Shoes", gender="Men"):
    pdata = {
        "product_id": "",
        "category": category,
        "gender": gender,
        "product_url": el.get("href", ""),
        "product_name": clean_text(el.get("name", "")),
        "brand": clean_text(el.get("brand", "")),
        "price": extract_price(el.get("price")),
        "original_price": extract_price(el.get("original_price")),
        "discount_percent": clean_text(el.get("discount", "")),
        "rating": clean_text(el.get("rating", "")) or "0",
        "reviews": clean_text(el.get("reviews", "")) or "0",
        "price_tier": "",
        "image_url": el.get("image", ""),
        "image_path": "",  # only relative path stored
        "source_platform": SOURCE_PLATFORM
    }

    # Extract ID
    if "/p/" in pdata["product_url"]:
        pdata["product_id"] = pdata["product_url"].split("/p/")[-1].split("?")[0]

    # Price tier
    p = pdata["price"]
    if p is None:
        pdata["price_tier"] = "unknown"
    elif p < 3000:
        pdata["price_tier"] = "affordable"
    elif p < 8000:
        pdata["price_tier"] = "mid"
    else:
        pdata["price_tier"] = "expensive"

    return pdata

# ---------------- SCRAPER ----------------
def scrape_ajio():
    all_products = []
    failed_extractions = 0
    category_counter = Counter()
    brand_counter = Counter()
    image_count = 0
    start_time = datetime.now()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(
            user_agent=random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/15.0 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/118.0"
            ])
        )

        for category, gender_map in keywords_map.items():
            for gender, keywords in gender_map.items():
                for keyword in keywords:
                    search_url = f"https://www.ajio.com/search/{keyword}"
                    console.print(f"[bold yellow]Scraping:[/bold yellow] {search_url}")

                    try:
                        page.goto(search_url, timeout=60000)
                        page.wait_for_selector("div.rilrtl-products-list__item", timeout=30000)
                    except:
                        console.print(f"[red]Failed to load {search_url}[/red]")
                        continue

                    # Infinite scroll
                    prev_count, stable_cycles, tries = 0, 0, 0
                    with Progress(SpinnerColumn(), TextColumn("[green]Scrolling[/green]"),
                                  BarColumn(), TimeElapsedColumn()) as progress:
                        task = progress.add_task("Scroll", total=MAX_SCROLL_TRIES)
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
                            progress.update(task, advance=1)

                    # Extract products
                    items = page.query_selector_all("div.rilrtl-products-list__item")
                    for item in items:
                        el_data = {
                            "href": item.query_selector("a.rilrtl-products-list__link.desktop").get_attribute("href") if item.query_selector("a.rilrtl-products-list__link.desktop") else "",
                            "name": item.query_selector("div.nameCls").inner_text() if item.query_selector("div.nameCls") else "",
                            "brand": item.query_selector("div.brand strong").inner_text() if item.query_selector("div.brand strong") else "",
                            "price": item.query_selector("span.price strong").inner_text() if item.query_selector("span.price strong") else "",
                            "original_price": item.query_selector("span.original-price").inner_text() if item.query_selector("span.original-price") else "",
                            "discount": item.query_selector("span.discount").inner_text() if item.query_selector("span.discount") else "",
                            "rating": "",
                            "reviews": "",
                            "image": item.query_selector("img.rilrtl-lazy-img").get_attribute("src") if item.query_selector("img.rilrtl-lazy-img") else ""
                        }

                        pdata = parse_product(el_data, category, gender)
                        if not pdata["product_name"]:
                            failed_extractions += 1
                            continue

                        if DOWNLOAD_IMAGES and pdata.get("image_url"):
                            folder_path, img_name, relative_path = generate_image_names(
                                pdata["product_name"], pdata["brand"], category, gender
                            )
                            local_path = download_image(page, pdata["image_url"], folder_path, img_name)
                            if local_path:
                                image_count += 1
                                pdata["image_path"] = relative_path

                        all_products.append(pdata)
                        category_counter[pdata["category"]] += 1
                        brand_counter[pdata["brand"]] += 1

        browser.close()

    # Save outputs
    df = pd.DataFrame(all_products)
    df.to_csv(CSV_FILENAME, index=False)
    with open(JSON_FILENAME, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    # Final summary
    end_time = datetime.now()
    total_products = len(all_products)
    success_rate = round(total_products / (total_products + failed_extractions) * 100, 2) if total_products > 0 else 0
    total_time = end_time - start_time
    products_per_minute = round(total_products / (total_time.total_seconds()/60), 2) if total_time.total_seconds() > 0 else 0

    console.print(Panel("[bold blue]Scraping Completed![/bold blue]"))
    console.print(f"Total Products Scraped: {total_products}")
    console.print(f"Failed Extractions: {failed_extractions}")
    console.print(f"Success Rate: {success_rate}%")
    console.print(f"Total Time: {total_time}")
    console.print(f"Products/Minute: {products_per_minute}")
    console.print(f"Images Downloaded: {image_count}")
    console.print(f"CSV Saved: {CSV_FILENAME}")
    console.print(f"JSON Saved: {JSON_FILENAME}")


if __name__ == "__main__":
    scrape_ajio()
