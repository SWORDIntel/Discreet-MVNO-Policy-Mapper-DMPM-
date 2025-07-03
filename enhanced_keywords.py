# Create enhanced_keywords.py for dynamic keyword generation
KEYWORD_TEMPLATES = [
    "{year} {mvno} activation requirements",
    "{mvno} prepaid sim {city} cash",
    "buy {mvno} sim card anonymous {year}",
    "{mvno} no id verification reddit",
    "{mvno} burner phone {forum_year}"
]

CITIES = ["NYC", "LA", "Chicago", "Houston", "Phoenix"]
FORUMS = ["reddit", "xda", "howardforums"]

# Generate temporal keywords
from datetime import datetime
current_year = datetime.now().year
forum_year = f"site:reddit.com/r/NoContract {current_year}"
