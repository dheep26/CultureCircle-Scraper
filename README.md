🌐 CultureCircle Scraper & Image Similarity Project
Overview

This project scrapes fashion product data from Culture Circle, downloads product images, and performs image similarity tests using OpenAI’s CLIP model.
The goal is to create a local product dataset with embeddings, which can later be used for recommendation systems, similarity search, or “look-alike” product games.

📦 Features

Scraping

Collects fashion products from Culture Circle based on predefined categories, genders, and keywords.

Extracts product name, brand, price, discounted price, category, gender, product URL, image URL, and price tiers.

Automatically downloads product images and organizes them into a clean folder structure.

Image Similarity

Uses CLIP (ViT-B/32) to generate embeddings for all product images.

Computes cosine similarity to find top visually similar products for a given query image.

Displays both query and top matches with images and metadata.

Output Formats

CSV and JSON of all scraped products (local_product_embeddings.xls/csv).

Organized image folders.

Notebook for testing similarity: includes embedding extraction, similarity search, and visualization.

🗂 Project Structure
CultureCircle-Scraper/
│
├─ logs/                   # Logs for scraper execution
├─ output/                 # Scraped data and images
│   ├─ images/             # Product images (by category/gender)
│   ├─ culturecircle_products_TIMESTAMP.csv
│   └─ culturecircle_products_TIMESTAMP.json
├─ notebooks/              # Jupyter notebooks for similarity testing
├─ scraper.py              # Main scraper script
├─ similarity_test.ipynb   # Notebook for testing CLIP embeddings
├─ requirements.txt        # Python dependencies
└─ README.md               # Project documentation

⚙️ Requirements

Install dependencies via pip:

pip install -r requirements.txt


Or, if you are using Conda (optional):

conda create -n culturecircle python=3.11
conda activate culturecircle
pip install -r requirements.txt

📝 Scraper Usage

Configure:

Update driver paths (EDGE_DRIVER_PATH or CHROME_DRIVER_PATH) in scraper.py.

Set output folder path if needed.

Run Scraper:

python scraper.py


Output:

CSV / JSON of products.

Images downloaded into structured folders:

images/
  ├─ Shoes/
  │   ├─ Women/
  │   ├─ Men/
  │   └─ Unisex/
  ├─ Bags/
  ├─ Accessories/
  └─ Clothing/

🔍 Image Similarity Notebook

The notebook similarity_test.ipynb allows you to:

Load your product dataset (local_product_embeddings.xls or CSV).

Extract embeddings using CLIP or read precomputed embeddings from the CSV.

Query an image and find top visually similar products.

Display images and metadata side by side for easy inspection.

Example usage in the notebook:

query_embedding = get_image_embedding(query_image_path)
top_products = find_similar_products(query_embedding, top_n=3)

for row in top_products.iterrows():
    display_product(row)

🛠 Technical Details
Component	Technology/Tool
Web scraping	Selenium, Requests, BeautifulSoup
Browser support	Edge, Chrome
Image processing	Pillow, OpenCV
Data handling	Pandas, NumPy
Similarity computation	CLIP (ViT-B/32), scikit-learn
Visualization	Matplotlib, Jupyter
Logging & Progress	logging, rich
💡 Tips

Headless mode: The scraper can run without opening a browser for faster execution.

Image download: If a download fails, the script retries automatically.

Price tiers: Products are classified as affordable, mid, or expensive based on price.

Similarity testing: Use the notebook to test both query images from your dataset or any external image.

⚠️ Notes

Make sure driver versions match your installed browser version.

For large datasets, GPU is recommended for faster CLIP embedding computations.

CSV should contain columns: emb_0 ... emb_511 for embeddings.

📌 Deliverables

Scraped product dataset (CSV + JSON).

Organized product images.

Similarity testing notebook with CLIP embeddings.

Documentation (this README).