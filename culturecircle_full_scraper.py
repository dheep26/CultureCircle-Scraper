import os
import time
import re
import json
import random
import shutil
import logging
from datetime import datetime
from typing import Optional

import requests
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import WebDriverException

# ---------------- CONFIG ----------------
EDGE_DRIVER_PATH = r"D:\CultureCircle-Scraper\CultureCircle-Scraper\msedgedriver.exe"
CHROME_DRIVER_PATH = None
BASE_URL = "https://culture-circle.com"
SEARCH_URL = BASE_URL + "/search?q="
SOURCE_PLATFORM = "Culture Circle"

OUT_PREFIX = "culturecircle"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = os.path.join(os.getcwd(), f"{OUT_PREFIX}_scrape_{TIMESTAMP}")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
CSV_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.csv")
JSON_FILENAME = os.path.join(OUTPUT_DIR, f"{OUT_PREFIX}_products_{TIMESTAMP}.json")

SCROLL_PAUSE_TIME = 1.5
MAX_SCROLL_TRIES = 200
NO_GROWTH_CYCLES = 5
DOWNLOAD_IMAGES = True

LOGS_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
console = Console()

# ---------------- LOGGER ----------------
def setup_logger(name="culturecircle_scraper"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    log_file = os.path.join(LOGS_DIR, f"{name}_{TIMESTAMP}.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger

logger = setup_logger()

# ---------------- DRIVER ----------------
def _user_agents():
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]

def create_driver(headless=True, timeout=20):
    try:
        if EDGE_DRIVER_PATH and os.path.exists(EDGE_DRIVER_PATH):
            opts = EdgeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument(f"--user-agent={random.choice(_user_agents())}")
            service = EdgeService(EDGE_DRIVER_PATH)
            driver = webdriver.Edge(service=service, options=opts)
            driver.set_page_load_timeout(timeout)
            return driver
        elif CHROME_DRIVER_PATH and os.path.exists(CHROME_DRIVER_PATH):
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument(f"--user-agent={random.choice(_user_agents())}")
            service = ChromeService(CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=opts)
            driver.set_page_load_timeout(timeout)
            return driver
        else:
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument(f"--user-agent={random.choice(_user_agents())}")
            driver = webdriver.Chrome(options=opts)
            driver.set_page_load_timeout(timeout)
            return driver
    except WebDriverException as e:
        logger.error(f"Failed to start webdriver: {e}")
        raise

# ---------------- UTILITIES ----------------
def clean_text(text: Optional[str]) -> str:
    return re.sub(r'\s+', ' ', text.strip()) if text else ""

def extract_price(price_text: str) -> Optional[float]:
    if not price_text:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else None
    except:
        return None

def generate_image_names(product_name: str, brand: str, category: str, gender: str):
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', (product_name or "").lower())
    clean_name = re.sub(r'\s+', '-', clean_name)[:60]
    clean_brand = re.sub(r'[^a-zA-Z0-9\s]', '', (brand or "nobrand").lower())
    clean_brand = re.sub(r'\s+', '-', clean_brand)[:30]
    folder_path = os.path.join(IMAGES_DIR, category, gender)
    image_name = f"{clean_name}-{clean_brand}.jpg"
    return folder_path, image_name

def download_image(image_url: str, folder_path: str, filename: str, max_attempts=2):
    if not image_url: return None
    os.makedirs(folder_path, exist_ok=True)
    local_path = os.path.join(folder_path, filename)
    if os.path.exists(local_path): return local_path
    headers = {"User-Agent": random.choice(_user_agents())}
    attempt = 0
    while attempt < max_attempts:
        try:
            resp = requests.get(image_url, headers=headers, stream=True, timeout=12)
            if resp.status_code == 200:
                with open(local_path, 'wb') as f:
                    resp.raw.decode_content = True
                    shutil.copyfileobj(resp.raw, f)
                return local_path
            else:
                attempt += 1
                time.sleep(1 + random.random())
        except Exception as e:
            logger.warning(f"Image download error {e} (attempt {attempt+1})")
            attempt += 1
            time.sleep(1 + random.random())
    return None

# ---------------- SCROLL ----------------
def infinite_scroll_load_all(driver, item_selector):
    prev_count = 0
    stable_cycles = 0
    tries = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]Scrolling...[/bold green]"),
        BarColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Scroll", total=MAX_SCROLL_TRIES)
        while tries < MAX_SCROLL_TRIES and stable_cycles < NO_GROWTH_CYCLES:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME + random.random()*0.8)
            items = driver.find_elements(By.CSS_SELECTOR, item_selector)
            curr_count = len(items)
            logger.info(f"Scroll {tries+1}: {curr_count} items")
            if curr_count == prev_count:
                stable_cycles += 1
            else:
                stable_cycles = 0
            prev_count = curr_count
            tries += 1
            progress.update(task, advance=1)
        return driver.find_elements(By.CSS_SELECTOR, item_selector)

# ---------------- PARSE PRODUCT ----------------
def parse_culture_item(element, category, gender):
    pdata = {
        "category": category,
        "gender": gender,
        "product_url": "",
        "product_name": "",
        "brand": "",
        "price": None,
        "discounted_price": None,
        "price_tier": "",
        "combined_tier": "",
        "image_url": "",
        "source_platform": SOURCE_PLATFORM
    }
    try:
        href = element.get_attribute("href") or ""
        pdata["product_url"] = BASE_URL + href if href.startswith("/") else href
        try:
            img = element.find_element(By.TAG_NAME, "img")
            pdata["image_url"] = img.get_attribute("src") or ""
            pdata["product_name"] = clean_text(img.get_attribute("alt") or "")
            if not pdata["brand"] and pdata["product_name"]:
                pdata["brand"] = pdata["product_name"].split()[0]
        except: pass

        # Extract prices using robust method
        try:
            spans = element.find_elements(By.CSS_SELECTOR, "div.flex.items-baseline.gap-1 span")
            for sp in spans:
                cls = sp.get_attribute("class") or ""
                txt = sp.text.replace(",", "").strip()
                if not txt: continue
                price_val = extract_price(txt)
                if "line-through" in cls:
                    pdata["price"] = price_val
                else:
                    pdata["discounted_price"] = price_val
            if pdata["price"] is None:
                pdata["price"] = pdata["discounted_price"]
        except: pass

        # Price tiers
        try:
            p = pdata.get("discounted_price") or pdata.get("price")
            if p is None:
                pdata["price_tier"] = "unknown"
            elif p < 3000:
                pdata["price_tier"] = "affordable"
            elif p < 8000:
                pdata["price_tier"] = "mid"
            else:
                pdata["price_tier"] = "expensive"
            pdata["combined_tier"] = pdata["price_tier"]
        except: pass

        return pdata
    except Exception as e:
        logger.warning(f"parse_culture_item warning: {e}")
        return pdata

# ---------------- FULL CATEGORIES & KEYWORDS ----------------
CATEGORIES = {
    "Shoes": {
        "Women": [
            "women+high+heels+designer", "women+sneakers+athletic", "women+boots+ankle",
            "women+sandals+summer", "women+loafers+formal", "women+wedges+casual",
            "women+flats+ballet", "women+platform+shoes", "women+espadrilles",
            "women+athletic+running", "women+hiking+boots", "women+rain+boots",
            "women+dress+shoes", "women+work+shoes", "women+dance+shoes",
            "women+wide+width+shoes", "women+orthopedic+shoes", "women+skate+shoes"
        ],
        "Men": [
            "men+sneakers+casual", "men+dress+shoes+formal", "men+boots+work",
            "men+sandals+slide", "men+loafers+driving", "men+oxfords",
            "men+derby+shoes", "men+trainers+gym", "men+hiking+shoes",
            "men+running+shoes", "men+boat+shoes", "men+chukka+boots",
            "men+chelsea+boots", "men+work+boots", "men+climbing+shoes",
            "men+wide+width+shoes", "men+orthopedic+shoes", "men+skate+shoes"
        ],
        "Unisex": [
            "unisex+sneakers", "unisex+slip+on", "unisex+canvas+shoes",
            "unisex+water+shoes", "unisex+skateboarding", "unisex+minimalist+shoes",
            "unisex+barefoot+shoes"
        ]
    },
    "Bags": {
        "Women": [
            "women+designer+handbags", "women+tote+bags+leather", "women+clutch+evening",
            "women+shoulder+bags", "women+backpack+travel", "women+crossbody+sling",
            "women+satchel+work", "women+belt Calabria+bags", "women+beach+bags",
            "women+laptop+backpacks", "women+minaudiere", "women+top+handle",
            "women+drawstring+bags", "women+evening+clutches", "women+quilted+bags"
        ],
        "Men": [
            "men+leather+messenger", "men+backpack+laptop", "men+briefcase+professional",
            "men+duffle+travel", "men+sling+bag", "men+gym+duffel",
            "men+shoulder+bag", "men+waist+pack", "men+tote+bag",
            "men+garment+bag", "men+tech+backpack", "men+travel+backpack",
            "men+camera+bag", "men+cycling+backpack", "men+fishing+vest"
        ],
        "Unisex": [
            "luggage+sets", "carry+on+luggage", "checked+luggage",
            "travel+backpacks", "duffel+bags+large", "laptop+backpacks+waterproof",
            "gym+duffels", "cooler+bags", "picnic+baskets",
            "compression+sacks", "dry+bags", "camera+backpacks",
            "hydration+packs", "tactical+backpacks", "rolling+backpacks"
        ]
    },
    "Accessories": {
        "Women": [
            "women+designer+sunglasses", "women+belts+leather", "women+scarves+silk",
            "women+statement+necklace", "women+designer+watches", "women+designer+wallets",
            "women+hair+accessories", "women+jewelry+sets", "women+brooches",
            "women+gloves", "women+hats+fashion", "women+stockings",
            "women+ties+scarves", "women+keychains", "women+tech+accessories"
        ],
        "Men": [
            "men+aviator+sunglasses", "men+leather+belts", "men+automatic+watches",
            "men+bifold+wallets", "men+designer+ties", "men+cufflinks+set",
            "men+pocket+squares", "men+hats+caps", "men+gloves+leather",
            "men+socks+dress", "men+tech+accessories", "men+keychains",
            "men+bracelets", "men+suspenders", "men+arm+sleeves"
        ],
        "Unisex": [
            "luxury+sunglasses", "designer+eyeglasses", "fitness+trackers",
            "smart+watches", "phone+cases+premium", "laptop+sleeves",
            "umbrellas+windproof", "travel+pillows", "blankets+throws",
            "gadget+accessories", "cables+organizers", "chargers+premium",
            "power+banks+fast", "headphones+wireless", "earbuds+premium"
        ]
    },
    "Clothing": {
        "Women": [
            "women+designer+dresses", "women+jackets+designer", "women+blouses+silk",
            "women+designer+jeans", "women+skirts+pleated", "women+sweaters+cashmere",
            "women+suits+pantsuits", "women+activewear+sets", "women+swimwear+designer",
            "women+lingerie+luxury", "women+coats+wool", "women+cardigans",
            "women+pajamas+silk", "women+shapewear", "women+maternity+dresses"
        ],
        "Men": [
            "men+designer+shirts", "men+jackets+bomber", "men+jeans+designer",
            "men+designer+t-shirts", "men+suits+designer", "men+sweaters+merino",
            "men+activewear+sets", "men+swim+trunks", "men+underwear+premium",
            "men+coats+overcoats", "men+vests+sleeveless", "men+pajamas",
            "men+robes", "men+base+layers", "men+formal+waistcoats"
        ],
        "Unisex": [
            "luxury+hoodies", "premium+sweatshirts", "designer+track+pants",
            "cashmere+robes", "silk+pajamas", "thermal+underwear",
            "rain+jackets", "down+jackets", "fleece+jackets",
            "performance+tees", "yoga+pants", "compression+wear",
            "sun+protective+clothing", "sports+bras", "cycling+shorts"
        ]
    }
}

# ---------------- MAIN ----------------
def scrape_culture_circle():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    driver = create_driver(headless=True)
    all_products = []
    summary = {}

    try:
        for category, genders in CATEGORIES.items():
            for gender, keywords in genders.items():
                for keyword in keywords:
                    console.print(Panel(f"[bold green]Searching keyword:[/bold green] {keyword}"))
                    driver.get(SEARCH_URL + keyword)
                    time.sleep(2 + random.random()*1.5)
                    items = infinite_scroll_load_all(driver, "a.flex.flex-col.gap-3.w-full")
                    console.print(f"[bold blue]Found {len(items)} products for '{keyword}'[/bold blue]")
                    summary[keyword] = len(items)

                    for el in items:
                        pdata = parse_culture_item(el, category, gender)
                        all_products.append(pdata)
                        if DOWNLOAD_IMAGES and pdata.get("image_url"):
                            folder_path, img_name = generate_image_names(
                                pdata.get("product_name"), pdata.get("brand"), category, gender
                            )
                            download_image(pdata["image_url"], folder_path, img_name)

        # Save outputs
        df = pd.DataFrame(all_products)
        df.to_csv(CSV_FILENAME, index=False)
        with open(JSON_FILENAME, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

        console.print(Panel(f"[bold blue]Scraping completed! Products saved to CSV and JSON[/bold blue]"))
        for k, v in summary.items():
            console.print(f"[green]{k}: {v} products scraped[/green]")
        console.print(f"[bold yellow]Total Products Scraped: {len(all_products)}[/bold yellow]")

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_culture_circle()
