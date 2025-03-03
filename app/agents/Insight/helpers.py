import re

def get_nested_dict_value(dictionary, *keys, default=None):
    """
    Safely gets a nested value from a dictionary.
    """
    current = dictionary
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def parse_collection_items(answer):
    """
    Converts a text answer into a list of items by cleaning and splitting on common delimiters.
    """
    items = []
    if answer:
        cleaned = re.sub(r'\d+\.\s*', '', answer)  # Remove numbered lists
        cleaned = re.sub(r'•\s*', '', cleaned)       # Remove bullet points
        cleaned = re.sub(r'-\s*', '', cleaned)         # Remove dashes
        for item in re.split(r'[,;]|\band\b', cleaned):
            item = item.strip()
            if item and len(item) > 1:
                items.append(item)
    return items

def parse_entry_id(entry_id):
    """Extract category and subcategory from the structured entry_id"""
    parts = entry_id.split('.')
    if len(parts) >= 3:
        return parts[0], parts[1]
    return None, None