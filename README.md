# Restro-Robot

A conversational AI assistant that provides detailed information about restaurants, menus, and dishes using a knowledge graph-based retrieval system.

> **Note**: Before using this system, you need to [collect restaurant data using the web scraper](./web_scrapper/README.md). This is a required first step.

## Features

- 🍽️ **Restaurant Menu Discovery**: Get complete menu information for specific restaurants
- 🌱 **Dietary Preference Support**: Find vegetarian and non-vegetarian options
- 📍 **Location-Based Search**: Filter results by location or area
- 🔍 **Semantic Search**: Natural language understanding for restaurant and food queries
- 💬 **Conversational Interface**: User-friendly chat experience

## System Overview

Restro-Robot consists of several integrated components:

1. **[Web Scraper](./web_scrapper/README.md)**: Collects restaurant menu data from EatSure
2. **Knowledge Graph Builder**: Processes raw data into a searchable knowledge graph
3. **Retrieval System**: Extracts relevant information based on user queries
4. **Conversational Interface**: Streamlit-based UI for natural interaction

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/tarangagrawal6/Zomato-Assignment.git
cd Zomato-Assignment
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
```

## Data Collection (Required First Step)

Before using the system, you need to collect restaurant data:

1. Run the web scraper to collect data from EatSure:
```bash
python web_scrapper/first.py  
python web_scrapper/seonding.py  
```

See the [Web Scraper README](./web_scrapper/README.md) for detailed instructions.

## Usage

### Starting the Chat Interface

After collecting data, you can start the chat interface:

```bash
streamlit run src/web/app.py
```

This will launch a Streamlit app in your browser where you can interact with the restaurant chatbot.

### Example Queries

- "What's on the menu at Behrouz Biryani?"
- "Show me vegetarian options "
- "Give me some good non-veg food recommendations"
- "What dishes does Faasos offer?"
- "Compare the menus of Behrouz Biryani and Faasos"
- "What's the price range for rolls at Faasos?"

## Architecture

Restro-Robot uses a knowledge graph retrieval system to process queries:

1. **Query Analysis**: Detects query type (menu, vegetarian, general) and extracts entities
2. **Entity Extraction**: Identifies restaurant names and locations
3. **Knowledge Graph Retrieval**: Fetches relevant information using direct lookups and semantic search
4. **Response Generation**: Returns formatted restaurant/menu information

## Project Structure

```
Zomato-Assignment/
├── src/
│   ├── web/
│   │   └── app.py             # Streamlit web interface
│   ├── chatbot/
│   │   └── chatbot.py         # Conversational interface
│   ├── retrieval/
│   │   └── kg_retriever.py    # Knowledge graph retrieval logic
│   ├── knowledge_base/
│   │   └── kg_builder.py      # Knowledge graph construction
│   └── utils/
│       ├── config.py
│       └── text_utils.py      # Helper functions
├── web_scrapper/              # Web scraping components
│   ├── first.py               # Area and restaurant discovery
│   ├── seonding.py            # Menu extraction
│   └── README.md              # Web scraper documentation
├── data/                      # Restaurant and menu data
│   └── eatsure_all_restaurants.json  # Scraped restaurant data           
└── README.md                  # This file
```

## Configuration

The system can be configured through environment variables:

- `GROQ_API_KEY`: Required for LLM functionality (LLaMa 3.3 70B by default)
- `MAX_RESULTS`: Maximum number of items to return (default: 10)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License - see the LICENSE file for details.
