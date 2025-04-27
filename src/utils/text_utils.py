import re

def normalize_name(name: str) -> str:
    """Lowercase and replace hyphens/underscores for matching."""
    if not name: return ""
    return name.lower().replace('-', ' ').replace('_', ' ')

def clean_text(text: str) -> str:
    """Text preprocessing pipeline"""
    if not text:
        return ""
    text = text.lower().replace('\n', ' ').replace('(', '').replace(')', '')
    # Remove non-alphanumeric characters except spaces, currency symbols, periods, commas, hyphens
    text = re.sub(r'[^\w\s₹$€£.,\-]', '', text)
    return ' '.join(text.split())

def parse_price(price_str: str) -> float:
    """Extract numeric price from string like '₹199'"""
    if not price_str: return 0.0
    # Handle potential ranges like '₹199 - ₹249' -> take the first price
    match = re.search(r'(\d+)', price_str)
    return float(match.group(1)) if match else 0.0