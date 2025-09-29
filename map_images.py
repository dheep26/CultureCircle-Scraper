import os

# Set the root directory you want to scan
root_dir = r"D:\CultureCircle-Scraper\CultureCircle-Scraper\culturecircle_scrape_20250918_094210\images"

# Allowed image extensions
image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')

# Initialize count
total_images = 0

# Walk through all folders and files
for foldername, subfolders, filenames in os.walk(root_dir):
    for file in filenames:
        if file.lower().endswith(image_extensions):
            total_images += 1

print(f"Total number of images: {total_images}")
