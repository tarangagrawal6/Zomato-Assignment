# Restro-Robot Web Scraper

This component collects restaurant and menu data from food delivery platforms to build the knowledge graph used by Restro-Robot.

## Overview

The web scraper is a multi-stage data collection pipeline focused on extracting structured data from EatSure and similar platforms:

1. **Area Discovery**: Identifies city areas with available restaurants
2. **Restaurant Discovery**: Collects restaurant listings within each area
3. **Menu Extraction**: Scrapes detailed menu items with prices and categorization
4. **Data Processing**: Organizes data by dietary preferences (veg/non-veg)

## Files

- `first.py`: City and area-level scraper that collects restaurant listings
- `seonding.py`: Menu-level scraper that extracts detailed dish information

## Setup

### Prerequisites

- Python 3.8+
- BeautifulSoup4
- Requests

### Installation

```bash
pip install beautifulsoup4 requests
```

## Usage

### 1. Area and Restaurant Discovery

```bash
python web_scrapper/first.py
```

This will:
- Prompt for a city name
- Create an `eatsure_data` directory
- Generate JSON files with area and restaurant data

### 2. Menu Extraction

```bash
python web_scrapper/seonding.py
```

This will:
- Prompt for the path to an area JSON file (e.g., `eatsure_data/bangalore_areas.json`)
- Extract menu items from each restaurant
- Separate items into vegetarian and non-vegetarian categories
- Save the complete dataset to the data directory

## Output Format

The final JSON output follows this structure:

```json
{
  "data": {
    "restaurant_slug": {
      "restaurant_name": "Restaurant Name",
      "url": "https://www.eatsure.com/restaurant/area",
      "veg": [
        {
          "section": "Section Name",
          "items": [
            {
              "url": "item_url",
              "name": "Dish Name",
              "price": "₹250",
              "description": "Description text",
              "is_nonveg": false
            }
          ]
        }
      ],
      "non_veg": [
        {
          "section": "Section Name",
          "items": [
            {
              "url": "item_url",
              "name": "Dish Name",
              "price": "₹350",
              "description": "Description text",
              "is_nonveg": true
            }
          ]
        }
      ]
    }
  }
}
```

## Data Integration

The collected data is stored in the project's data directory for use by the knowledge graph builder.

## Legal Considerations

This scraper is for educational and research purposes only. Always:
- Respect the site's robots.txt
- Implement reasonable rate limiting
- Check terms of service before scraping
- Do not use scraped data commercially without permission