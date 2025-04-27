import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

BASE_URL = "https://www.eatsure.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


session = requests.Session()
session.headers.update(HEADERS)


def slugify(url):
    """Filesystem-safe slug from URL path."""
    path = urlparse(url).path.rstrip('/')
    return path.lstrip('/').replace('/', '_')

def extract_restaurant_slug(url):
    m = re.match(r"https?://[^/]+/([^/]+)/[^/]+/[^/]+", url)
    return m.group(1) if m else None


def clean_text(text):
    """Trim and collapse whitespace."""
    return text.strip().replace('\n', ' ') if text else ''


def fetch_restaurant_menu(restaurant_url):
    """
    Scrape menu sections and dish details for one restaurant.
    Returns:
        List[Dict]: each dict has 'section' and 'items' list.
    """
    r = session.get(restaurant_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    menu = []
    current_section = None

   
    for elem in soup.find_all(['h2', 'a']):
        if elem.name == 'h2':
            title = clean_text(elem.get_text())
            if title:
                current_section = {'section': title, 'items': []}
                menu.append(current_section)
        elif elem.name == 'a' and elem.has_attr('id') and elem['id'].startswith('product_'):
            if current_section is None:
                current_section = {'section': 'Menu', 'items': []}
                menu.append(current_section)

            href = elem['href']
            full_url = urljoin(BASE_URL, href)

            name_el    = elem.select_one('[data-qa="productName"]')
            price_el   = elem.select_one('[data-qa="totalPrice"]')
            if( price_el is None):
                price_el = elem.select_one('[data-qa="slashedPrice"]')
            desc_el    = elem.select_one('[data-qa="productInfo"]')
            nonveg_el  = elem.select_one('[data-qa="isNonVeg"]')

            is_nonveg = nonveg_el is not None
            item = {
                'url':         full_url,
                'name':        clean_text(name_el.get_text())  if name_el  else '',
                'price':       clean_text(price_el.get_text()) if price_el else '',
                'description': clean_text(desc_el.get_text())  if desc_el  else '',
                'is_nonveg':   is_nonveg
            }
            current_section['items'].append(item)

    return menu


def partition_menu(menu):
    veg_sections = []
    nonveg_sections = []

    for sec in menu:
        veg_items = [i for i in sec['items'] if not i['is_nonveg']]
        nonveg_items = [i for i in sec['items'] if i['is_nonveg']]
        if veg_items:
            veg_sections.append({'section': sec['section'], 'items': veg_items})
        if nonveg_items:
            nonveg_sections.append({'section': sec['section'], 'items': nonveg_items})

    return veg_sections, nonveg_sections


def main():
    area_file = input("Path to area JSON file: ").strip()
    with open(area_file, 'r', encoding='utf-8') as f:
        restaurants = json.load(f)

    # Create a dictionary to hold all restaurant data
    all_data = {"data": {}}
    
    # Process each restaurant
    for rest in restaurants:
        url = rest.get('url', '')
        name = extract_restaurant_slug(url)
        if not url:
            continue

        print(f"→ Processing {name} -> {url}")
        try:
            slug = slugify(url)
            full_menu = fetch_restaurant_menu(url)
            veg_menu, nonveg_menu = partition_menu(full_menu)

            restaurant_data = {
                'restaurant_name': name,
                'url': url,
                'veg': veg_menu,
                'non_veg': nonveg_menu
            }
            
            # Add to all_data dictionary using slug as key
            all_data["data"][slug] = restaurant_data
            
            print(f"   • Added {name} to combined data")
        except Exception as e:
            print(f"   ✗ Error scraping {url}: {e}")
    
    # Save combined data to a single file
    output_file = "eatsure_all_restaurants.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved {len(all_data['data'])} restaurants to {output_file}")

if __name__ == '__main__':
    main()