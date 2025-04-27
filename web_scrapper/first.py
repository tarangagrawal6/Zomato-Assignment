import re
import time
import json
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class EatSureScraper:
    def __init__(self):
        self.base_url = "https://www.eatsure.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        os.makedirs("eatsure_data", exist_ok=True)

    def get_areas_for_city(self, city):
        """Scrape the city page for area links."""
        city_slug = city.lower().replace(" ", "-")
        url = f"{self.base_url}/{city_slug}-restaurants"
        resp = self.session.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        areas = []
        for a in soup.find_all("a", href=True):
            m = re.match(rf"/{city_slug}/([\w-]+)$", a["href"])
            if m:
                slug = m.group(1)
                name = a.get_text().strip()
                if name and slug:
                    full = urljoin(self.base_url, a["href"])
                    areas.append({"name": name, "slug": slug, "url": full})
        # dedupe
        unique = {area["slug"]: area for area in areas}
        return list(unique.values())

    def get_restaurants_for_area(self, area):
        """Scrape one area page for restaurant links."""
        resp = self.session.get(area["url"])
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        links = []
        for a in soup.select("a[href]"):
            href = a["href"]
            # Match pattern like "/the-good-bowl/lucknow/hazratganj"
            if re.match(r"^/[\w-]+/[\w-]+/[\w-]+$", href):
                full = urljoin(self.base_url, href)
                name = a.get_text().strip() or "Unknown"
                links.append({"name": name, "url": full})
        seen = set()
        unique = []
        for r in links:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)
        return unique


    def scrape_city(self, city):
        print(f"Scraping areas for {city}…")
        areas = self.get_areas_for_city(city)
        self._save(f"eatsure_data/{city}_areas.json", areas)

        all_data = {"city": city, "areas": []}
        for area in areas:
            print(f" → {area['name']}")
            time.sleep(1)
            restos = self.get_restaurants_for_area(area)
            all_data["areas"].append({
                "name": area["name"],
                "slug": area["slug"],
                "restaurants": restos
            })
            self._save(f"eatsure_data/{area['slug']}_restaurants.json", restos)

        self._save(f"eatsure_data/{city}_all.json", all_data)
        print("Done. Data in eatsure_data/")

    def _save(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    city = input("City to scrape: ")
    EatSureScraper().scrape_city(city)