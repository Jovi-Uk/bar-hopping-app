# =============================================================================
# Natural Language Understanding Service (FIXED - Robust None handling)
# =============================================================================

import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple

# Bar name aliases - maps common names/typos to official names
BAR_ALIASES = {
    # Chimy's variations
    "chimy's": "Chimy's",
    "chimys": "Chimy's",
    "chimmys": "Chimy's",
    "chimmy's": "Chimy's",
    "chimmies": "Chimy's",
    "chimies": "Chimy's",
    "chimi's": "Chimy's",
    "chimis": "Chimy's",
    
    # Cricket's variations
    "cricket's": "Cricket's",
    "crickets": "Cricket's",
    "cricketts": "Cricket's",
    "crikets": "Cricket's",
    "criket's": "Cricket's",
    
    # Bier Haus variations
    "bier haus": "Bier Haus",
    "bierhaus": "Bier Haus",
    "beer haus": "Bier Haus",
    "beerhaus": "Bier Haus",
    "bier house": "Bier Haus",
    "beer house": "Bier Haus",
    
    # Logie's variations
    "logie's": "Logie's",
    "logies": "Logie's",
    "logeys": "Logie's",
    "logi's": "Logie's",
    "logis": "Logie's",
    
    # Atomic variations
    "atomic": "Atomic",
    "atomics": "Atomic",
    "atomic's": "Atomic",
    
    # Bar PM variations
    "bar pm": "Bar PM",
    "barpm": "Bar PM",
    "bar p.m.": "Bar PM",
    "pm bar": "Bar PM",
    
    # Wrecked variations
    "wrecked": "Wrecked",
    "wreckd": "Wrecked",
    "rekt": "Wrecked",
    
    # Miguel's variations  
    "miguel's": "Miguel's",
    "miguels": "Miguel's",
    "miguel": "Miguel's",
    "miguell's": "Miguel's",
    
    # Crafthouse variations
    "crafthouse": "Crafthouse",
    "craft house": "Crafthouse",
    "the crafthouse": "Crafthouse",
    
    # Bikini's variations
    "bikini's": "Bikini's",
    "bikinis": "Bikini's",
    "bikinnis": "Bikini's",
}

# List of all valid bar names
VALID_BARS = [
    "Chimy's",
    "Cricket's", 
    "Bier Haus",
    "Logie's",
    "Atomic",
    "Bar PM",
    "Wrecked",
    "Miguel's",
    "Crafthouse",
    "Bikini's"
]


def fuzzy_match_bar(query: str, threshold: float = 0.7) -> Tuple[Optional[str], float]:
    """Find the best matching bar name using fuzzy matching."""
    if not query:
        return None, 0.0
        
    query_lower = query.lower().strip()
    
    # Direct alias match
    if query_lower in BAR_ALIASES:
        return BAR_ALIASES[query_lower], 1.0
    
    # Fuzzy match against valid bars
    best_match = None
    best_score = 0.0
    
    for bar in VALID_BARS:
        bar_lower = bar.lower()
        score = SequenceMatcher(None, query_lower, bar_lower).ratio()
        
        # Boost score if query is substring
        if query_lower in bar_lower or bar_lower in query_lower:
            score = max(score, 0.85)
        
        if score > best_score:
            best_score = score
            best_match = bar
    
    if best_score >= threshold:
        return best_match, best_score
    
    return None, 0.0


def extract_bars_from_text(text: str) -> List[str]:
    """Extract bar names from natural language text."""
    if not text:
        return []
        
    found_bars = []
    text_lower = text.lower()
    
    # Strategy 1: Check for direct alias matches
    for alias, bar_name in BAR_ALIASES.items():
        if alias in text_lower and bar_name not in found_bars:
            found_bars.append(bar_name)
    
    # Strategy 2: Check individual words with fuzzy matching
    words = re.findall(r"\b[\w']+\b", text)
    for word in words:
        if len(word) >= 3:
            bar, score = fuzzy_match_bar(word)
            if bar and bar not in found_bars and score > 0.75:
                found_bars.append(bar)
    
    # Strategy 3: Check bigrams (two-word combinations)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        bar, score = fuzzy_match_bar(bigram)
        if bar and bar not in found_bars and score > 0.75:
            found_bars.append(bar)
    
    return found_bars


def extract_time(text: str) -> float:
    """Extract time from text. ALWAYS returns a valid float (defaults to 21.0 = 9 PM)."""
    if not text:
        return 21.0
    
    text_lower = text.lower()
    
    # Pattern: "9pm", "9 pm", "9:30pm"
    match = re.search(r'(\d{1,2}):?(\d{2})?\s*(pm|am)', text_lower)
    if match:
        hour = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
            
        return float(hour) + (minutes / 60.0)
    
    # Pattern: "at 9", "around 8"
    match = re.search(r'(?:at|around|like|@)\s*(\d{1,2})(?::(\d{2}))?', text_lower)
    if match:
        hour = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        
        if 1 <= hour <= 11:
            hour += 12
            
        return float(hour) + (minutes / 60.0)
    
    # Pattern: standalone time near time words
    if any(word in text_lower for word in ['tonight', 'evening', 'night', 'pm']):
        match = re.search(r'\b(\d{1,2})\b', text_lower)
        if match:
            hour = int(match.group(1))
            if 1 <= hour <= 11:
                hour += 12
            return float(hour)
    
    return 21.0


def extract_group_size(text: str) -> int:
    """Extract group size from text. ALWAYS returns a valid int (defaults to 2)."""
    if not text:
        return 2
        
    text_lower = text.lower()
    
    match = re.search(r'me\s+and\s+(\d+)', text_lower)
    if match:
        return int(match.group(1)) + 1
    
    match = re.search(r'(?:group|party)\s+of\s+(\d+)', text_lower)
    if match:
        return int(match.group(1))
    
    match = re.search(r'(\d+)\s+(?:people|friends|of us)', text_lower)
    if match:
        return int(match.group(1))
    
    return 2


def detect_game_day(text: str) -> bool:
    """Detect if the request mentions game day."""
    if not text:
        return False
        
    game_keywords = ['game day', 'gameday', 'game night', 'football', 'basketball', 
                     'tech game', 'red raiders', 'raiders game']
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in game_keywords)


def parse_user_request(text: str) -> Dict:
    """Main NLU function - parse user request. GUARANTEED valid values."""
    if not text or not text.strip():
        return {
            "bars": [],
            "start_time": 21.0,
            "group_size": 2,
            "is_game_day": False,
            "raw_text": "",
            "parse_success": False
        }
    
    bars = extract_bars_from_text(text)
    start_time = extract_time(text)
    group_size = extract_group_size(text)
    is_game_day = detect_game_day(text)
    
    # SAFETY: Ensure all values are valid types
    if start_time is None or not isinstance(start_time, (int, float)):
        start_time = 21.0
    start_time = float(start_time)
    if start_time < 17:
        start_time = start_time + 12 if start_time < 12 else 21.0
    
    if group_size is None or not isinstance(group_size, int):
        group_size = 2
    group_size = max(1, min(int(group_size), 20))
    
    return {
        "bars": bars if bars else [],
        "start_time": start_time,
        "group_size": group_size,
        "is_game_day": bool(is_game_day),
        "raw_text": text,
        "parse_success": len(bars) > 0
    }
