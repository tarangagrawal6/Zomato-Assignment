import os
import re
from typing import Tuple

from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA

# Use absolute imports
from src.knowledge_base.kg_builder import RestaurantKG
from src.retrieval.kg_retriever import KGRetriever
from src.chatbot.prompts import CUSTOM_RAG_PROMPT 
from src.utils.text_utils import normalize_name
class RestaurantChatbot:
    def __init__(self, kg: RestaurantKG):
        self.kg = kg
        self.history = [] 
        try:
            groq_api_key = os.environ.get("GROQ_API_KEY")
            if not groq_api_key:
                 raise ValueError("GROQ_API_KEY environment variable not set.")
            # Consider making model name configurable
            self.llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.7, groq_api_key=groq_api_key)
            print("Groq LLM (llama3-8b-8192) initialized successfully.")
        except Exception as e:
            print(f"ERROR initializing Groq LLM: {e}. Ensure GROQ_API_KEY is set correctly.")
            # Decide if the app should stop or try to continue without LLM for some queries
            raise ValueError("Could not initialize LLM.") from e

        self.retriever = KGRetriever(kg=self.kg, k=5)
        self.rag_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff", 
            retriever=self.retriever,
            chain_type_kwargs={"prompt": CUSTOM_RAG_PROMPT}, 
            return_source_documents=False 
        )
        print("LangChain RAG chain initialized.")

    def _handle_query_type(self, query: str) -> str:
        """Determine the type of query to decide the handling strategy."""
        q = query.lower()
        if 'compare' in q and 'menus' in q and 'and' in q:
            return 'desc_compare'
        if 'vegetarian' in q and ('best' in q or 'most' in q):
            return 'veg_comparison'
        # Price range needs careful extraction
        if 'price' in q and 'range' in q and ('for' in q or 'of' in q or 'at' in q):

            if self._extract_restaurant_and_section(query)[0]:
                 return 'price_range'
        if 'gluten' in q and ('have' in q or 'offer' in q or 'any' in q or 'at' in q or 'in' in q):
             if self._extract_restaurant_and_section(query)[0]:
                  return 'gluten_free_specific'
             else:
                  return 'gluten_free_general' 
        if 'gluten' in q: 
            return 'gluten_free_general'

    
        if 'what' in q and ('offer' in q or 'have' in q or 'serve' in q) and \
           ('appetizers' in q or 'desserts' in q or 'dishes' in q or 'items' in q):
             return 'availability_rag' 

        # Default to general RAG handling
        return 'general_rag'

    def _extract_restaurants_and_keyword(self, query: str) -> Tuple[str | None, str | None, str | None]:
        """Extract restaurant names and keyword from comparison queries."""
        rest_matches = re.findall(r'menus? of ([\w\s&]+) and ([\w\s&]+)', query, re.IGNORECASE)
        keyword = None
        m = re.search(r'compare the ([\w\s]+) mentioned', query, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            words = phrase.split()
            keyword = words[-1]
            if keyword in ['levels', 'options']: keyword = words[-2]
            if keyword == 'dishes' and len(words) > 1: keyword = words[-2]
            if keyword in ['the', 'a', 'an']: keyword = words[-2] if len(words) > 1 else None
        if not keyword and 'spice' in query.lower(): keyword = 'spice'
        if not keyword:
             m = re.search(r'([a-zA-Z0-9\-]+) (?:dishes|mentioned)', query, re.IGNORECASE)
             if m: keyword = m.group(1)

        if rest_matches and keyword:
            rest1, rest2 = rest_matches[0]
            return rest1.strip(), rest2.strip(), keyword.lower()
        elif rest_matches:
             print("Warning: Found restaurants for comparison but couldn't extract keyword.")
             rest1, rest2 = rest_matches[0]
             return rest1.strip(), rest2.strip(), None
        return None, None, keyword.lower() if keyword else None

    def _extract_restaurant_and_section(self, query: str) -> Tuple[str | None, str | None]:
         """Extract restaurant and optional section for price/gluten queries."""
         q_lower = query.lower()
         patterns = [
              r'(?:price range|gluten-free)\s+(?:for|at|in)\s+([\w\s\-&]+?)(?:\'s)?(?:\s+([\w\s]+?))?\s*(?:menu)?$',
              r'(?:gluten-free|price range)\s+([\w\s]+?)\s+(?:at|for)\s+([\w\s\-&]+)$'
         ]
         for i, pattern in enumerate(patterns):
              match = re.search(pattern, q_lower)
              if match:
                   groups = match.groups()
                   if i == 0:
                        rest = groups[0].strip() if groups[0] else None
                        sect = groups[1].strip() if groups[1] else None
                        return rest, sect
                   elif i == 1:
                        sect = groups[0].strip() if groups[0] else None
                        rest = groups[1].strip() if groups[1] else None
                        if sect and len(sect.split()) > 1 and any(w.istitle() for w in sect.split()):
                             rest, sect = sect, rest
                        return rest, sect

         potential_rests = re.findall(r'\b[A-Z][\w\s\-&\'\.]+\b', query)
         if potential_rests:
              longest_rest = max(potential_rests, key=len).strip()
              section_match = re.search(rf'{re.escape(longest_rest)}\s+(dessert|appetizer|main|drink|starter)s?', query, re.IGNORECASE)
              section = section_match.group(1) if section_match else None
              return longest_rest, section
         return None, None

    def ask(self, query: str) -> str:
        """Handle user query, routing to KG methods or RAG chain."""
        self.history.append({"role": "user", "content": query}) # Basic history
        qtype = self._handle_query_type(query)
        print(f"DEBUG: Query: '{query}' -> Type: {qtype}")

        # --- Structured Handlers (Direct KG Access) ---
        if qtype == 'veg_comparison':
            veg_counts = self.kg.get_veg_counts()
            if not veg_counts: return "No vegetarian options found."
            sorted_veg = sorted(veg_counts.items(), key=lambda item: item[1], reverse=True)
            answer = "Based on item counts:\n"
            for rest, count in sorted_veg[:5]: answer += f"• {rest}: {count} veg items\n"
            if sorted_veg: answer += f"\n'{sorted_veg[0][0]}' has the most listed veg items."
            return answer

        elif qtype == 'gluten_free_specific':
             restaurant, section = self._extract_restaurant_and_section(query)
             # We already checked restaurant exists in _handle_query_type
             gluten_free_items = self.kg.get_gluten_free_items(restaurant, section)
             if not gluten_free_items:
                  return f"No specific gluten-free options found {f'in {section} ' if section else ''}at '{restaurant}' based on descriptions. (Check common ingredients)."
             answer = f"Potentially gluten-free options {f'in {section} ' if section else ''}at '{restaurant}':\n"
             for item in gluten_free_items[:7]: answer += f"• {item['name']} (₹{item['price']:.0f})\n"
             if len(gluten_free_items) > 7: answer += f"... and {len(gluten_free_items) - 7} more."
             answer += "\n(Note: Verify with restaurant for strict needs.)"
             return answer

        elif qtype == 'gluten_free_general':
             gluten_free_items = self.kg.get_gluten_free_items()
             if not gluten_free_items: return "No specific gluten-free options found across restaurants based on descriptions."
             answer = "Some potentially gluten-free options:\n"
             by_rest = {}
             for item in gluten_free_items:
                  rest_name = item['restaurant_name']
                  if rest_name not in by_rest: by_rest[rest_name] = []
                  if len(by_rest[rest_name]) < 2: by_rest[rest_name].append(f"{item['name']} (₹{item['price']:.0f})")
             for rest, items_list in list(by_rest.items())[:4]: answer += f"\n{rest}:\n" + "\n".join([f"• {i}" for i in items_list])
             if len(by_rest) > 4: answer += f"\n... and potentially more."
             answer += "\n(Note: Verify with restaurant for strict needs.)"
             return answer

        elif qtype == 'price_range':
            restaurant, section = self._extract_restaurant_and_section(query)
            # We already checked restaurant exists in _handle_query_type
            return self.kg.get_price_range(restaurant, section)

        elif qtype == 'desc_compare':
            rest1, rest2, keyword = self._extract_restaurants_and_keyword(query)
            norm1 = normalize_name(rest1) if rest1 else None
            norm2 = normalize_name(rest2) if rest2 else None

            # Gather menu items for both
            items1 = [e for e in self.kg.entities if e['type'] == 'MenuItem' and e['normalized_restaurant_name'] == norm1]
            items2 = [e for e in self.kg.entities if e['type'] == 'MenuItem' and e['normalized_restaurant_name'] == norm2]

            if not items1 and not items2:
                return f"Sorry, I couldn't find data for either '{rest1}' or '{rest2}'."
            if not items1:
                return f"Sorry, I couldn't find data for '{rest1}'."
            if not items2:
                return f"Sorry, I couldn't find data for '{rest2}'."

            # Build context for RAG
            context1 = "\n".join(
                f"{e['name']} ({e['section']}, ₹{e['price']:.0f})"
                for e in items1[:30]
            )
            context2 = "\n".join(
                f"{e['name']} ({e['section']}, ₹{e['price']:.0f})"
                for e in items2[:30]
            )
            compare_prompt = (
                f"Compare the following two restaurants based on their menu, price range, and variety. "
                f"Highlight unique items and similarities.\n\n"
                f"{rest1.title()} Menu:\n{context1}\n\n"
                f"{rest2.title()} Menu:\n{context2}\n"
            )
            try:
                rag_response = self.rag_chain.invoke({"query": compare_prompt}).get("result", "").strip()
                # If RAG fails, fallback to structured comparison
                if not rag_response or "not available" in rag_response.lower() or len(rag_response) < 20:
                    # Structured fallback
                    menu_size1 = len(items1)
                    menu_size2 = len(items2)
                    veg1 = sum(1 for e in items1 if e['dietary'] == 'veg')
                    veg2 = sum(1 for e in items2 if e['dietary'] == 'veg')
                    nonveg1 = menu_size1 - veg1
                    nonveg2 = menu_size2 - veg2
                    prices1 = [e['price'] for e in items1 if e['price'] > 0]
                    prices2 = [e['price'] for e in items2 if e['price'] > 0]
                    price_range1 = f"₹{min(prices1):.0f} - ₹{max(prices1):.0f}" if prices1 else "N/A"
                    price_range2 = f"₹{min(prices2):.0f} - ₹{max(prices2):.0f}" if prices2 else "N/A"
                    from collections import Counter
                    section1 = Counter([e['section'] for e in items1]).most_common(3)
                    section2 = Counter([e['section'] for e in items2]).most_common(3)
                    ex_items1 = ", ".join([e['name'] for e in items1[:3]])
                    ex_items2 = ", ".join([e['name'] for e in items2[:3]])
                    names1 = set(e['name'].lower() for e in items1)
                    names2 = set(e['name'].lower() for e in items2)
                    common_dishes = names1 & names2
                    common_dishes_str = ", ".join(dish.title() for dish in list(common_dishes)[:5]) if common_dishes else "None"
                    answer = (
                        f"**Comparison between {rest1.title()} and {rest2.title()}:**\n\n"
                        f"**Menu Size:**\n"
                        f"- {rest1.title()}: {menu_size1} items\n"
                        f"- {rest2.title()}: {menu_size2} items\n\n"
                        f"**Veg/Non-Veg Count:**\n"
                        f"- {rest1.title()}: {veg1} veg, {nonveg1} non-veg\n"
                        f"- {rest2.title()}: {veg2} veg, {nonveg2} non-veg\n\n"
                        f"**Price Range:**\n"
                        f"- {rest1.title()}: {price_range1}\n"
                        f"- {rest2.title()}: {price_range2}\n\n"
                        f"**Popular Sections:**\n"
                        f"- {rest1.title()}: {', '.join([s[0] for s in section1 if s[0]])}\n"
                        f"- {rest2.title()}: {', '.join([s[0] for s in section2 if s[0]])}\n\n"
                        f"**Sample Items:**\n"
                        f"- {rest1.title()}: {ex_items1}\n"
                        f"- {rest2.title()}: {ex_items2}\n\n"
                        f"**Common Dishes:** {common_dishes_str}\n"
                    )
                    return answer
                return rag_response
            except Exception as e:
                print(f"Error invoking RAG chain for comparison: {e}")
                return "Sorry, I couldn't generate a comparison at this time."

        # --- RAG Handler ---
        if qtype == 'availability_rag' or qtype == 'general_rag':
            print(f"DEBUG: Using RAG chain for query type '{qtype}'")
            try:
                result = self.rag_chain.invoke({"query": query})
                answer = result.get("result", "").strip()

                # Check for unhelpful RAG responses
                if not answer or \
                   'don\'t know' in answer.lower() or \
                   'cannot answer' in answer.lower() or \
                   'outside the scope' in answer.lower() or \
                   'not available in the provided details' in answer.lower() or \
                   len(answer) < 20:
                     # Try simple KG search as fallback
                     kg_results = self.kg.search(query, k=3)
                     if kg_results:
                          fallback_answer = "Based on keywords, found related items:\n"
                          for item in kg_results: fallback_answer += f"• At {item['restaurant_name']}: {item['name']} (₹{item['price']:.0f})\n"
                          return fallback_answer
                     else:
                          return "Information not found for your query." # Keep it concise
                return answer

            except Exception as e:
                print(f"Error invoking RAG chain: {e}")
                return f"Error processing request: {str(e)[:100]}"

        # Should not be reached
        return "Sorry, I encountered an issue handling your query."
