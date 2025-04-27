import streamlit as st
import os
import sys
import re
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.utils.config import load_config
from src.knowledge_base.kg_builder import RestaurantKG
from src.chatbot.chatbot import RestaurantChatbot  


load_dotenv()

config = load_config()
data_path = os.path.join('data', 'eatsure_all_restaurants.json')


@st.cache_resource
def load_kg():
    import json
    with open(data_path, 'r') as f:
        data = json.load(f)["data"]
    return RestaurantKG(data, kg_cache_path="kg_cache")

kg = load_kg()

@st.cache_resource
def load_rag_chatbot():
    return RestaurantChatbot(kg)

rag_chatbot = load_rag_chatbot()

def answer_query(kg, rag_chatbot, query):
    q = query.lower()

    # --- Structured KG logic ---
    if "appetizer" in q and "offer" in q:
        m = re.search(r'does (.+?) offer', q)
        rest = m.group(1) if m else None
        if rest:
            items = [
                e for e in kg.entities
                if e['type'] == 'MenuItem'
                and e['normalized_restaurant_name'] == rest.strip().lower()
                and ("appetizer" in e['section'].lower() or "appetizer" in e['name'].lower())
            ]
            if items:
                return f"Appetizers at {rest}:\n" + "\n".join(f"- {i['name']} (₹{i['price']:.0f})" for i in items)
            else:
                return f"No appetizers found for {rest}."
        else:
            return "Could not determine the restaurant name from your query."

    if "vegetarian" in q and ("best" in q or "most" in q):
        veg_counts = kg.get_veg_counts()
        if not veg_counts: return "No vegetarian options found."
        sorted_veg = sorted(veg_counts.items(), key=lambda item: item[1], reverse=True)
        answer = "Based on item counts:\n"
        for rest, count in sorted_veg[:5]: answer += f"• {rest}: {count} veg items\n"
        if sorted_veg: answer += f"\n'{sorted_veg[0][0]}' has the most listed veg items."
        return answer

    if "gluten" in q:
        gluten_free_items = kg.get_gluten_free_items()
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

    if "price range" in q and ("for" in q or "of" in q or "at" in q):
        m = re.search(r'price range (?:for|of|at) (.+)', q)
        target = m.group(1).strip() if m else None
        if target:
            rest_price = kg.get_price_range(target)
            if "Could not find restaurant" in rest_price or "no valid price information" in rest_price.lower():
                results = [e for e in kg.entities if e['type'] == 'MenuItem' and target.lower() in e['name'].lower()]
                prices = [e['price'] for e in results if e['price'] > 0]
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    if min_price == max_price:
                        return f"'{target.title()}' items seem to be priced at ₹{min_price:.0f}."
                    return f"Price range for '{target.title()}' items is ₹{min_price:.0f} - ₹{max_price:.0f}."
                faiss_results = kg.search(target, k=10)
                prices = [e['price'] for e in faiss_results if e['price'] > 0]
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    if min_price == max_price:
                        return f"'{target.title()}' items (by semantic search) seem to be priced at ₹{min_price:.0f}."
                    return f"Price range for '{target.title()}' items (by semantic search) is ₹{min_price:.0f} - ₹{max_price:.0f}."
                return f"Sorry, I couldn't find price information for '{target}'."
            else:
                return rest_price
        else:
            return "Could not determine the restaurant or item name for price range."

    # --- RAG-powered Comparison logic ---
    if "compare" in q and ("between" in q or "and" in q):
        m = re.search(r'compare (?:between )?(.+?) and (.+)', q)
        if m:
            rest1 = m.group(1).strip()
            rest2 = m.group(2).strip()
            # Retrieve top menu/context for both restaurants
            context1 = "\n".join(
                f"{e['name']} ({e['section']}, ₹{e['price']:.0f})"
                for e in kg.entities
                if e['type'] == 'MenuItem' and rest1.lower() in e['normalized_restaurant_name']
            )[:1500]
            context2 = "\n".join(
                f"{e['name']} ({e['section']}, ₹{e['price']:.0f})"
                for e in kg.entities
                if e['type'] == 'MenuItem' and rest2.lower() in e['normalized_restaurant_name']
            )[:1500]
            if not context1 and not context2:
                return f"Sorry, I couldn't find data for either '{rest1}' or '{rest2}'."
            if not context1:
                return f"Sorry, I couldn't find data for '{rest1}'."
            if not context2:
                return f"Sorry, I couldn't find data for '{rest2}'."
            # Compose a comparison prompt for RAG
            compare_prompt = (
                f"Compare the following two restaurants based on their menu, price range, and variety. "
                f"Highlight unique items and similarities.\n\n"
                f"{rest1.title()} Menu:\n{context1}\n\n"
                f"{rest2.title()} Menu:\n{context2}\n"
            )
            rag_response = rag_chatbot.ask(compare_prompt)
            if rag_response and rag_response.strip():
                return rag_response
            else:
                return "Sorry, I couldn't generate a comparison at this time."

    # --- Fallback: RAG-based semantic search ---
    try:
        rag_response = rag_chatbot.ask(query)
        if rag_response and rag_response.strip():
            return rag_response
    except Exception as e:
        print(f"RAG fallback error: {e}")

    # --- Final fallback: simple KG search ---
    results = kg.search(query, k=5)
    if results:
        return "Related menu items:\n" + "\n".join(f"- {i['restaurant_name']}: {i['name']} (₹{i['price']:.0f})" for i in results)
    return "Sorry, I couldn't find an answer for your query."
# --- Streamlit UI (unchanged) ---
st.markdown(
    """
        <style>
            .appview-container .main .block-container {
                padding-top: 1rem;
                padding-bottom: 1rem;
            }
        </style>""",
    unsafe_allow_html=True,
)

st.markdown("""
    <h3 style='text-align: left; color: white; padding-top: 35px; border-bottom: 3px solid orange;'>
        Discover Local Restaurants & Menus 🍽️🥘
    </h3>""", unsafe_allow_html=True)

side_bar_message = """
Hi! 👋 I'm your restaurant guide for Lucknow. What would you like to know about local restaurants?

Here are some areas you might be interested in:
1. **Restaurant Information** 🏢
2. **Menu Recommendations** 🍲
3. **Vegetarian Options** 🥗
4. **Spice Level Preferences** 🌶️
5. **Popular Dishes** ⭐

Feel free to ask me anything about the restaurants in our database!
"""

with st.sidebar:
    st.title('🤖RestroBot: Your Local Restaurant Guide')
    st.markdown(side_bar_message)

initial_message = """
    Hi there! I'm your RestroBot 🤖
    Here are some questions you might ask me:\n
    🍽️ Tell me about dishes in Behrouz Biryani menu ?\n
    🍽️ What vegetarian options are available?\n
    🍽️ Can you recommend some spicy dishes?\n
    🍽️ Give me lowest price roll in faasos?
"""

if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": initial_message}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def clear_chat_history():
    st.session_state.messages = [{"role": "assistant", "content": initial_message}]

st.button('Clear Chat', on_click=clear_chat_history)

if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Finding the best food recommendations for you..."):
            response = answer_query(kg, rag_chatbot, prompt)
            placeholder = st.empty()
            full_response = response
            placeholder.markdown(full_response)
    message = {"role": "assistant", "content": full_response}
    st.session_state.messages.append(message)