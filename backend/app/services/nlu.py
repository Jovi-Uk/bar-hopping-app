# =============================================================================
# backend/app/services/nlu.py
# =============================================================================
# This service handles Natural Language Understanding (NLU). It takes messy,
# casual human language like "yo wanna hit chimys and crickets tonight at 9pm"
# and extracts structured data: bars=["Chimy's", "Cricket's"], time=21.0
#
# Key capabilities:
# - Bar name recognition with fuzzy matching (handles "chimys" → "Chimy's")
# - Time extraction from various formats ("9pm", "21:00", "around 8")
# - Group size detection ("me and 5 friends" → 6 people)
# - Game day detection for special event handling
# =============================================================================

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any


# =============================================================================
# Bar Name Aliases
# =============================================================================
# This dictionary maps the many ways people might type or say a bar name
# to the canonical (official) name. The keys are lowercase for matching.

BAR_ALIASES = {
    # Chimy's and variations
    "chimy's": "Chimy's",
    "chimys": "Chimy's",
    "chimmy's": "Chimy's",
    "chimmys": "Chimy's",
    "chimy": "Chimy's",
    "chimmy": "Chimy's",
    "chimeys": "Chimy's",
    "chimmeys": "Chimy's",
    
    # Cricket's and variations
    "cricket's": "Cricket's",
    "crickets": "Cricket's",
    "cricket": "Cricket's",
    "cricketts": "Cricket's",
    
    # Bier Haus and variations
    "bier haus": "Bier Haus",
    "bierhaus": "Bier Haus",
    "beer haus": "Bier Haus",
    "beerhaus": "Bier Haus",
    "beer house": "Bier Haus",
    "bier house": "Bier Haus",
    
    # Atomic and variations
    "atomic": "Atomic",
    "atomic bar": "Atomic",
    
    # Bar PM and variations
    "bar pm": "Bar PM",
    "barpm": "Bar PM",
    "bar p.m.": "Bar PM",
    "pm bar": "Bar PM",
    
    # Misquetes and variations
    "misquetes": "Misquetes",
    "misquitos": "Misquetes",
    "mosquitos": "Misquetes",
    "misquites": "Misquetes",
    
    # Wrecked and variations
    "wrecked": "Wrecked",
    "wreckd": "Wrecked",
    "wreck'd": "Wrecked",
    
    # The Library and variations
    "the library": "The Library",
    "library": "The Library",
    "lib": "The Library",
    
    # Bash's and variations
    "bash's": "Bash's",
    "bashs": "Bash's",
    "bash": "Bash's",
    "bashes": "Bash's",
    
    # Electric Avenue and variations
    "electric avenue": "Electric Avenue",
    "electric ave": "Electric Avenue",
    "electric": "Electric Avenue",
    "e ave": "Electric Avenue",
    
    # Roadhouse and variations
    "roadhouse": "Roadhouse",
    "road house": "Roadhouse",
}

# List of all canonical bar names (no duplicates)
ALL_BARS = list(set(BAR_ALIASES.values()))


def fuzzy_match_bar(text: str, threshold: float = 0.7) -> Optional[str]:
    """
    Find the best matching bar name using fuzzy string matching.
    
    This function is called when an exact alias match isn't found. It compares
    the input text against all known bar names and aliases using the
    Ratcliff/Obershelp algorithm (good for detecting typos).
    
    Args:
        text: The text to match against bar names
        threshold: Minimum similarity (0.0-1.0) to consider a match
    
    Returns:
        The canonical bar name if found, None otherwise
    
    Example:
        fuzzy_match_bar("chimeys") → "Chimy's"
    """
    text_lower = text.lower().strip()
    best_match = None
    best_ratio = threshold
    
    # Check against all aliases
    for alias, canonical in BAR_ALIASES.items():
        ratio = SequenceMatcher(None, text_lower, alias).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = canonical
    
    # Also check canonical names directly
    for bar_name in ALL_BARS:
        ratio = SequenceMatcher(None, text_lower, bar_name.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = bar_name
    
    return best_match


def extract_bars_from_text(text: str) -> List[str]:
    """
    Extract all mentioned bar names from the input text.
    
    Uses multiple strategies:
    1. Direct alias matching (fastest, handles known variations)
    2. Fuzzy matching for typos
    3. Pattern matching for compound names like "bier haus"
    
    Args:
        text: The user's natural language request
    
    Returns:
        List of canonical bar names found (no duplicates)
    
    Example:
        extract_bars_from_text("let's hit chimys and crickets")
        → ["Chimy's", "Cricket's"]
    """
    found_bars = set()  # Use set to avoid duplicates
    text_lower = text.lower()
    
    # Strategy 1: Check for direct alias matches
    # Sort by length (longest first) to match "bier haus" before "bier"
    sorted_aliases = sorted(BAR_ALIASES.keys(), key=len, reverse=True)
    
    for alias in sorted_aliases:
        # Use word boundary check to avoid partial matches
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, text_lower):
            found_bars.add(BAR_ALIASES[alias])
    
    # Strategy 2: Fuzzy match individual words and bigrams
    words = text_lower.split()
    
    # Check single words (skip common words)
    skip_words = {'the', 'a', 'an', 'and', 'or', 'at', 'to', 'for', 'with', 
                  'let', 'lets', "let's", 'hit', 'go', 'want', 'wanna'}
    
    for word in words:
        if word in skip_words or len(word) < 3:
            continue
        match = fuzzy_match_bar(word, threshold=0.75)
        if match:
            found_bars.add(match)
    
    # Check bigrams (two-word combinations)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        match = fuzzy_match_bar(bigram, threshold=0.7)
        if match:
            found_bars.add(match)
    
    return list(found_bars)


def extract_time(text: str) -> Optional[float]:
    """
    Extract the start time from natural language text.
    
    Handles various formats:
    - 12-hour: "9pm", "9:30 PM", "9 p.m."
    - 24-hour: "21:00", "2100"
    - Casual: "around 8", "at nine"
    
    Args:
        text: The user's natural language request
    
    Returns:
        Time as decimal hours (9.5 = 9:30), or None if not found
        Times are in 24-hour format (21.0 = 9 PM)
    
    Example:
        extract_time("let's meet at 9:30pm") → 21.5
    """
    text_lower = text.lower()
    
    # Pattern 1: HH:MM AM/PM (most specific)
    pattern_12h_minutes = r'(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)'
    match = re.search(pattern_12h_minutes, text_lower)
    if match:
        hour = int(match.group(1))
        minutes = int(match.group(2))
        period = match.group(3)
        
        if 'pm' in period or 'p.m' in period:
            if hour != 12:
                hour += 12
        elif hour == 12:
            hour = 0
        
        return hour + (minutes / 60.0)
    
    # Pattern 2: H AM/PM (no minutes)
    pattern_12h = r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)'
    match = re.search(pattern_12h, text_lower)
    if match:
        hour = int(match.group(1))
        period = match.group(2)
        
        if 'pm' in period or 'p.m' in period:
            if hour != 12:
                hour += 12
        elif hour == 12:
            hour = 0
        
        return float(hour)
    
    # Pattern 3: 24-hour format
    pattern_24h = r'\b(1[0-9]|2[0-3]):?([0-5][0-9])\b'
    match = re.search(pattern_24h, text_lower)
    if match:
        hour = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        return hour + (minutes / 60.0)
    
    # Pattern 4: Number with context words
    context_words = ['at', 'around', 'by', 'after', 'before', 'starting']
    for context_word in context_words:
        pattern = context_word + r'\s+(\d{1,2})(?:\s|$|,)'
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            # Assume PM for bar hopping context
            if hour < 12 and hour >= 1:
                hour += 12
            if 17 <= hour <= 23:
                return float(hour)
    
    # Pattern 5: Word numbers
    word_to_num = {
        'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12
    }
    for word, num in word_to_num.items():
        if word in text_lower:
            hour = num if num >= 12 else num + 12
            if 17 <= hour <= 23:
                return float(hour)
    
    return None


def extract_group_size(text: str) -> int:
    """
    Extract group size from natural language text.
    
    Handles various phrasings:
    - "me and 5 friends" → 6
    - "party of 6" → 6
    - "with 3 people" → 4 (speaker + 3)
    - "just the two of us" → 2
    
    Args:
        text: The user's natural language request
    
    Returns:
        Group size as integer (minimum 1, default 2)
    """
    text_lower = text.lower()
    
    # Pattern 1: "X friends" (add 1 for speaker)
    match = re.search(r'(\d+)\s*(?:friends?|buddies?|pals?)', text_lower)
    if match:
        return int(match.group(1)) + 1
    
    # Pattern 2: "me and X friends"
    match = re.search(r'me\s+and\s+(\d+)', text_lower)
    if match:
        return int(match.group(1)) + 1
    
    # Pattern 3: "party/group of X"
    match = re.search(r'(?:party|group|team)\s+of\s+(\d+)', text_lower)
    if match:
        return int(match.group(1))
    
    # Pattern 4: "X people"
    match = re.search(r'(\d+)\s*(?:people|persons?|of us)', text_lower)
    if match:
        return int(match.group(1))
    
    # Pattern 5: Word numbers
    word_numbers = {
        'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    for word, num in word_numbers.items():
        if f'{word} of us' in text_lower or f'the {word} of us' in text_lower:
            return num
    
    return 2  # Default


def detect_game_day(text: str) -> bool:
    """
    Detect if the request mentions a game day or special event.
    
    Game days in Lubbock (Texas Tech football) significantly increase
    bar crowds and wait times.
    
    Args:
        text: The user's natural language request
    
    Returns:
        True if game day indicators are found
    """
    text_lower = text.lower()
    
    game_indicators = [
        'game day', 'gameday', 'game night',
        'football', 'tech game', 'red raiders',
        'big game', 'after the game',
        'tailgate', 'tailgating'
    ]
    
    for indicator in game_indicators:
        if indicator in text_lower:
            return True
    
    return False


def parse_user_request(text: str) -> Dict[str, Any]:
    """
    Parse a natural language request into structured data.
    
    This is the main entry point for the NLU service. It combines all
    extraction functions to produce a complete understanding of the
    user's request.
    
    Args:
        text: The user's natural language request
    
    Returns:
        Dictionary with:
        - bars: List of canonical bar names
        - start_time: Decimal hours or None
        - group_size: Number of people
        - is_game_day: Boolean
        - original_text: The input text
    
    Example:
        parse_user_request("yo wanna hit chimys and crickets at 9pm")
        → {
            "bars": ["Chimy's", "Cricket's"],
            "start_time": 21.0,
            "group_size": 2,
            "is_game_day": False,
            "original_text": "yo wanna hit chimys and crickets at 9pm"
        }
    """
    return {
        "bars": extract_bars_from_text(text),
        "start_time": extract_time(text),
        "group_size": extract_group_size(text),
        "is_game_day": detect_game_day(text),
        "original_text": text
    }
