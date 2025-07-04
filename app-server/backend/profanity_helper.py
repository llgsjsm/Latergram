import os
import json
import re

def load_profanity_list(filename):
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, filename)

    with open(full_path, 'r') as f:
        words = json.load(f)
        return set(word.strip().lower() for word in words if isinstance(word, str) and word.strip())


PROFANE_WORDS = load_profanity_list('words.json')
def check_profanity(text):
    words = re.findall(r'\b\w+\b', text.lower())
    return any(word in PROFANE_WORDS for word in words)

