from typing import Dict, List, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import os
import pickle
from src.utils.text_utils import normalize_name, clean_text, parse_price

class RestaurantKG:
    def __init__(
        self,
        data: Optional[Dict] = None,
        kg_cache_path: str = "kg_cache",
        model_name: str = 'all-MiniLM-L6-v2'
    ):
        self.model_name = model_name
        self.model = SentenceTransformer(self.model_name)
        self.kg_cache_path = kg_cache_path
        self.entities = []
        self.menuitem_indices = []
        self.index = None

        if self._kg_cache_exists():
            self._load_kg_cache()
            print("Knowledge Graph and FAISS index loaded from cache.")
        elif data is not None:
            self.data = data
            self._build_knowledge_graph()
            self._save_kg_cache()
            print("Knowledge Graph and FAISS index built and cached.")
        else:
            raise ValueError("No data provided and no cache found.")

    def _kg_cache_exists(self):
        return (
            os.path.exists(f"{self.kg_cache_path}_entities.pkl") and
            os.path.exists(f"{self.kg_cache_path}_menuitem_indices.pkl") and
            os.path.exists(f"{self.kg_cache_path}_faiss.index")
        )

    def _save_kg_cache(self):
        with open(f"{self.kg_cache_path}_entities.pkl", "wb") as f:
            pickle.dump(self.entities, f)
        with open(f"{self.kg_cache_path}_menuitem_indices.pkl", "wb") as f:
            pickle.dump(self.menuitem_indices, f)
        faiss.write_index(self.index, f"{self.kg_cache_path}_faiss.index")

    def _load_kg_cache(self):
        with open(f"{self.kg_cache_path}_entities.pkl", "rb") as f:
            self.entities = pickle.load(f)
        with open(f"{self.kg_cache_path}_menuitem_indices.pkl", "rb") as f:
            self.menuitem_indices = pickle.load(f)
        self.index = faiss.read_index(f"{self.kg_cache_path}_faiss.index")

    def _parse_key(self, key: str) -> Tuple[str, str]:
        parts = key.split('_')
        if len(parts) > 1:
            name = parts[0]
            location = ' '.join(p.capitalize() for p in parts[1:])
            return name, location
        return key, ""

    def _build_knowledge_graph(self):
        menuitem_embeddings = []
        print("Starting Knowledge Graph construction...")
        for restaurant_id, details in self.data.items():
            rest_name_from_key, location_from_key = self._parse_key(restaurant_id)
            rest_name = details.get('restaurant_name', rest_name_from_key)
            if not rest_name:
                continue
            rest_entity = {
                'id': restaurant_id,
                'type': 'Restaurant',
                'name': rest_name,
                'normalized_name': normalize_name(rest_name),
                'location': location_from_key,
                'url': details.get('url', '')
            }
            self.entities.append(rest_entity)
            for section_type in ['veg', 'non_veg']:
                if section_type in details:
                    for section in details[section_type]:
                        section_name = section.get('section', '')
                        for item in section.get('items', []):
                            item_name = item.get('name', '')
                            if not item_name:
                                continue
                            entity = {
                                'id': f"{restaurant_id}_{item_name}".replace(" ", "_").replace("/", "_"),
                                'type': 'MenuItem',
                                'restaurant_id': restaurant_id,
                                'restaurant_name': rest_name,
                                'normalized_restaurant_name': normalize_name(rest_name),
                                'section': section_name,
                                'name': item_name,
                                'price': parse_price(item.get('price', '')),
                                'description': clean_text(item.get('description', '')),
                                'dietary': 'non-veg' if item.get('is_nonveg', False) else 'veg',
                                'location': location_from_key
                            }
                            self.entities.append(entity)
                            current_entity_index = len(self.entities) - 1
                            self.menuitem_indices.append(current_entity_index)
                            embed_text = (
                                f"{entity['restaurant_name']} {entity['section']} {entity['name']} "
                                f"{entity['description']} Location: {entity['location']} Dietary: {entity['dietary']}"
                            )
                            embedding = self.model.encode(embed_text)
                            menuitem_embeddings.append(embedding)
        if menuitem_embeddings:
            menuitem_embeddings = np.array(menuitem_embeddings, dtype=np.float32)
            dimension = menuitem_embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(menuitem_embeddings)
            print(f"FAISS index built with {len(menuitem_embeddings)} menu items.")
        else:
            self.index = None
            print("Warning: No menu items found to build FAISS index.")
        print("Knowledge Graph construction finished.")

    def search(self, query: str, k=10, location_filter: Optional[str] = None) -> List[Dict]:
        """Semantic search over menu items using FAISS index, optionally filtering by location."""
        if not self.index or not self.menuitem_indices:
            print("Warning: Search called but index is not available.")
            return []
        try:
            query_embed = self.model.encode(query)
            _, relative_indices = self.index.search(np.array([query_embed], dtype=np.float32), k * 5)
            results = []
            for i in relative_indices[0]:
                if 0 <= i < len(self.menuitem_indices):
                    global_entity_index = self.menuitem_indices[i]
                    entity = self.entities[global_entity_index]
                    if location_filter:
                        if location_filter.lower() not in entity.get('location', '').lower():
                            continue
                    results.append(entity)
                    if len(results) >= k:
                        break
            # Remove duplicates and sort by price if relevant
            seen = set()
            unique_results = []
            for r in results:
                key = (r['restaurant_name'], r['name'])
                if key not in seen:
                    unique_results.append(r)
                    seen.add(key)
            return unique_results
        except Exception as e:
            print(f"FAISS search error: {e}")
            return []

    def get_veg_options(self, restaurant_name: Optional[str] = None, location: Optional[str] = None) -> List[Dict]:
        """Return all vegetarian menu items, optionally filtered by restaurant and/or location."""
        veg_items = []
        norm_rest_name = normalize_name(restaurant_name) if restaurant_name else None
        for entity in self.entities:
            if entity['type'] == 'MenuItem' and entity['dietary'] == 'veg':
                if norm_rest_name and entity['normalized_restaurant_name'] != norm_rest_name:
                    continue
                if location and location.lower() not in entity.get('location', '').lower():
                    continue
                veg_items.append(entity)
        return veg_items

    def get_menu_items_for_restaurant(self, restaurant_name: str, location: Optional[str] = None) -> List[Dict]:
        """Return all menu items for a given restaurant, optionally filtered by location."""
        norm_rest_name = normalize_name(restaurant_name)
        items = []
        for entity in self.entities:
            if entity['type'] == 'MenuItem' and entity['normalized_restaurant_name'] == norm_rest_name:
                if location and location.lower() not in entity.get('location', '').lower():
                    continue
                items.append(entity)
        return items

    def get_restaurants_in_location(self, location: str) -> List[str]:
        """Returns a list of unique restaurant names found in a specific location."""
        if not location: return []
        norm_location = location.lower()
        names = set()
        for entity in self.entities:
            entity_location = entity.get('location', '').lower()
            if norm_location in entity_location:
                name_to_add = entity.get('name') if entity.get('type') == 'Restaurant' else entity.get('restaurant_name')
                if name_to_add:
                    names.add(name_to_add)
        return sorted(list(names))
    # Add this method to your RestaurantKG class
    def get_price_range(self, restaurant_name: str, location: Optional[str] = None) -> str:
        """Returns the price range for a given restaurant."""
        norm_rest_name = normalize_name(restaurant_name)
        prices = []
        
        for entity in self.entities:
            if entity['type'] == 'MenuItem' and entity['normalized_restaurant_name'] == norm_rest_name:
                if location and location.lower() not in entity.get('location', '').lower():
                    continue
                if entity.get('price', 0) > 0:
                    prices.append(entity['price'])
        
        if not prices:
            exists = any(e for e in self.entities if e.get('type') == 'Restaurant' and e.get('normalized_name') == norm_rest_name)
            if exists:
                loc_str = f" in {location}" if location else ""
                return f"No price information available for {restaurant_name}{loc_str}."
            else:
                return f"Restaurant '{restaurant_name}' not found in database."
        
        min_price = min(prices)
        max_price = max(prices)
        
        loc_str = f" in {location}" if location else ""
        if min_price == max_price:
            return f"Items at {restaurant_name}{loc_str} are priced at ₹{min_price:.0f}."
        else:
            return f"Price range for {restaurant_name}{loc_str} is ₹{min_price:.0f} - ₹{max_price:.0f}."