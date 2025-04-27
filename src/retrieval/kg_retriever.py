from typing import List, Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
import re
from src.knowledge_base.kg_builder import RestaurantKG

class KGRetriever(BaseRetriever):
    """Retriever that uses the RestaurantKG for semantic and direct lookup."""
    
    kg: RestaurantKG
    k: int = 10  # Default number of documents to retrieve
    
    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query using improved patterns."""
        patterns = [
            r'(?:in|at|near)\s+([\w\s\-&\']+?)(?:\s+(?:area|locality|region|zone))',  # With area terms
            r'(?:in|at|near)\s+([\w\s\-&\']+?)(?:\?|$|\.|\s+menu|\s+restaurant)',     # Standard pattern with boundaries
            r'(?:in|at|near)\s+the\s+([\w\s\-&\']+?)(?:\s|\?|$|\.)',                  # With "the" included
        ]
        
        for pattern in patterns:
            m = re.search(pattern, query, re.IGNORECASE)
            if m:
                location = m.group(1).strip()
                # Validate: Avoid matching restaurant names as locations
                if "biryani" in location.lower() or "bowl" in location.lower() or "faasos" in location.lower():
                    continue
                return location
        return None

    def _extract_restaurant(self, query: str) -> Optional[str]:
        """Extract restaurant name using multiple patterns for robustness."""
        patterns = [
            r'(?:dishes|items|food)\s+(?:in|at|from|of)\s+([\w\s\-&\'\.]+?)(?:\s+menu|\s+restaurant|\?|$|\.)',  # "dishes in X"
            r'([\w\s\-&\'\.]+?)(?:\s+menu|\s+dishes|\s+restaurant|\s+food)(?:\s|\?|$|\.)',  # "X menu"
            r'(?:about|tell me about)\s+([\w\s\-&\'\.]+?)(?:\s+menu|\s+restaurant|\s+food|\?|$|\.)',  # "about X"
            r'(?:about|tell me about)\s+([\w\s\-&\'\.]+)',  
        ]
        
        for pattern in patterns:
            m = re.search(pattern, query, re.IGNORECASE)
            if m:
                restaurant = m.group(1).strip()
                # Remove articles and common prefixes
                restaurant = re.sub(r'^(?:the|a|an)\s+', '', restaurant, flags=re.IGNORECASE)
                return restaurant
        return None

    def _is_vegetarian_query(self, query: str) -> bool:
        """Check if query is asking about vegetarian options."""
        lower_query = query.lower()
        
        # First check if it's explicitly non-vegetarian
        if ('non-veg' in lower_query or 
            'non veg' in lower_query or
            'nonveg' in lower_query):
            print(">>> Detected non-vegetarian query")  # Added debug print
            return False
            
        # More carefully check vegetarian patterns to avoid matching "non veg food" as "veg food"
        veg_patterns = [
            r'\bvegetarian\b',
            r'\bveg\s+option',
            r'\bveg\s+food',
            r'\bveg\s+dish'
        ]
        
        for pattern in veg_patterns:
            if re.search(pattern, lower_query):
                return True
        
        return False

    def _is_menu_query(self, query: str) -> bool:
        """Check if query is asking about a restaurant's menu."""
        lower_query = query.lower()
        return ('menu' in lower_query or 
                'dish' in lower_query or 
                'what do they serve' in lower_query or 
                'what do they offer' in lower_query)
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Retrieve relevant documents from the RestaurantKG."""
        print(f"\n>>> Processing query: '{query}'")
        
        # STEP 1: Categorize the query
        is_veg_query = self._is_vegetarian_query(query)
        is_menu_query = self._is_menu_query(query)
        
        # STEP 2: Extract entities from query
        location = self._extract_location(query)
        restaurant_name = self._extract_restaurant(query) if is_menu_query else None
        
        print(f">>> Query analysis: vegetarian={is_veg_query}, menu={is_menu_query}")
        print(f">>> Extracted: restaurant='{restaurant_name}', location='{location}'")
        
        # STEP 3: Retrieve relevant items based on query type
        items = []
        
        # Case 1: Restaurant Menu Query
        if is_menu_query and restaurant_name:
            # Direct lookup by restaurant name
            items = self.kg.get_menu_items_for_restaurant(restaurant_name, location=location)
            print(f">>> Direct restaurant lookup found {len(items)} items for '{restaurant_name}'")
            
            # Try with normalized name if needed
            if not items:
                normalized_name = restaurant_name.lower().replace('-', ' ').replace('_', ' ')
                print(f">>> Trying with normalized name: '{normalized_name}'")
                items = self.kg.get_menu_items_for_restaurant(normalized_name, location=location)
                print(f">>> Normalized lookup found {len(items)} items")
            
            # Try a partial match if still no results
            if not items:
                print(f">>> No direct match, trying partial name matching")
                for entity in self.kg.entities:
                    if (entity['type'] == 'Restaurant' and 
                        restaurant_name.lower() in entity['name'].lower()):
                        print(f">>> Found partial match: {entity['name']}")
                        items = self.kg.get_menu_items_for_restaurant(entity['name'], location=location)
                        if items:
                            break
                print(f">>> Partial matching found {len(items)} items")
            
            # Final fallback to semantic search
            if not items:
                print(">>> All direct lookups failed, using semantic search")
                items = self.kg.search(f"{restaurant_name} menu items", k=self.k*2)
        
        # Case 2: Vegetarian Options Query
        elif is_veg_query:
            items = self.kg.get_veg_options(location=location)
            print(f">>> Vegetarian query found {len(items)} items")
            
            # If no items found or too many, limit or try semantic search
            if len(items) > 20:
                items = items[:20]  # Limit to 20 items
            elif not items:
                print(">>> No veg items found, trying semantic search")
                items = self.kg.search("vegetarian dishes", k=self.k)
        
        # Case 3: General Query
        else:
            items = self.kg.search(query, k=self.k, location_filter=location)
            print(f">>> General semantic search found {len(items)} items")
        
        # STEP 4: Convert items to documents
        # STEP 4: Convert items to documents (existing code)
        documents = []
        for item in items:
            content = (
                f"Restaurant: {item.get('restaurant_name', 'N/A')}\n"
                f"Location: {item.get('location', 'N/A')}\n"
                f"Item: {item.get('name', 'N/A')}\n"
                f"Section: {item.get('section', 'N/A')}\n"
                f"Price: ₹{item.get('price', 0):.0f}\n"
                f"Dietary: {item.get('dietary', 'N/A')}\n"
                f"Description: {item.get('description', 'N/A')}"
            )
            metadata = {
                'restaurant_name': item.get('restaurant_name', 'N/A'),
                'item_name': item.get('name', 'N/A'),
                'price': item.get('price', 0),
                'section': item.get('section', 'N/A'),
                'dietary': item.get('dietary', 'N/A'),
                'location': item.get('location', 'N/A'),
                'id': item.get('id', 'N/A')
            }
            documents.append(Document(page_content=content, metadata=metadata))

        # ADD THIS TOKEN LIMITING CODE:
        if is_menu_query and len(documents) > 15:
            print(f">>> Too many items ({len(documents)}), sampling representative items...")
            # Group by section
            sections = {}
            for doc in documents:
                section = doc.metadata['section'] 
                if section not in sections:
                    sections[section] = []
                sections[section].append(doc)
            
            # Take a few items from each section
            sampled_docs = []
            for section, docs in sections.items():
                sampled_docs.extend(docs[:3])  # Take up to 3 items per section
            
            documents = sampled_docs[:15]  # Take at most 15 total
            print(f">>> Reduced to {len(documents)} representative items")

        print(f">>> Returning {len(documents)} documents for LLM context\n")
        return documents