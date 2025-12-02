# =============================================================================
# Route Simulation & Optimization Service (FIXED - Robust None handling)
# =============================================================================

from typing import List, Dict, Optional, Tuple
from itertools import permutations

# Bar data - capacities, popularity, base wait times, hours
BAR_ROSTER = {
    "Chimy's": {
        "capacity": 200,
        "popularity": 5,
        "base_wait": 15,
        "hours": {"default": (17, 2), "fri": (17, 2), "sat": (17, 2)}
    },
    "Cricket's": {
        "capacity": 150,
        "popularity": 4,
        "base_wait": 10,
        "hours": {"default": (18, 2), "fri": (18, 2), "sat": (18, 2)}
    },
    "Bier Haus": {
        "capacity": 120,
        "popularity": 4,
        "base_wait": 8,
        "hours": {"default": (17, 1), "fri": (17, 2), "sat": (17, 2)}
    },
    "Logie's": {
        "capacity": 100,
        "popularity": 3,
        "base_wait": 5,
        "hours": {"default": (18, 1), "fri": (18, 2), "sat": (18, 2)}
    },
    "Atomic": {
        "capacity": 80,
        "popularity": 3,
        "base_wait": 5,
        "hours": {"default": (19, 2), "fri": (19, 2), "sat": (19, 2)}
    },
    "Bar PM": {
        "capacity": 100,
        "popularity": 3,
        "base_wait": 7,
        "hours": {"default": (20, 2), "fri": (20, 2), "sat": (20, 2)}
    },
    "Wrecked": {
        "capacity": 90,
        "popularity": 2,
        "base_wait": 3,
        "hours": {"default": (18, 1), "fri": (18, 2), "sat": (18, 2)}
    },
    "Miguel's": {
        "capacity": 110,
        "popularity": 3,
        "base_wait": 6,
        "hours": {"default": (17, 0), "fri": (17, 1), "sat": (17, 1)}
    },
    "Crafthouse": {
        "capacity": 130,
        "popularity": 4,
        "base_wait": 10,
        "hours": {"default": (16, 0), "fri": (16, 1), "sat": (16, 1)}
    },
    "Bikini's": {
        "capacity": 85,
        "popularity": 2,
        "base_wait": 4,
        "hours": {"default": (18, 1), "fri": (18, 2), "sat": (18, 2)}
    }
}

# Constants
TRAVEL_TIME = 7  # minutes between bars
STAY_DURATION = 60  # minutes at each bar
GAME_DAY_MULTIPLIER = 1.5

# Hourly traffic multipliers
HOURLY_TRAFFIC = {
    17: 1.0, 18: 1.0, 19: 1.3, 20: 1.5,
    21: 2.0, 22: 2.0, 23: 1.8, 0: 1.5, 1: 1.2, 2: 1.0
}


def safe_float(value, default: float = 21.0) -> float:
    """Safely convert to float with default."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 2) -> int:
    """Safely convert to int with default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_time(decimal_hour: float) -> str:
    """Convert decimal hour to HH:MM format. Handles None safely."""
    decimal_hour = safe_float(decimal_hour, 21.0)
    
    # Handle times past midnight
    if decimal_hour >= 24:
        decimal_hour -= 24
    
    hours = int(decimal_hour)
    minutes = int((decimal_hour - hours) * 60)
    return f"{hours:02d}:{minutes:02d}"


def is_bar_open(bar_name: str, time: float) -> bool:
    """Check if a bar is open at the given time. Handles None safely."""
    time = safe_float(time, 21.0)
    
    if bar_name not in BAR_ROSTER:
        return False
    
    bar = BAR_ROSTER[bar_name]
    open_hour, close_hour = bar["hours"]["default"]
    
    # Handle overnight hours (e.g., 17-2 means 5pm to 2am)
    if close_hour < open_hour:
        # Bar is open overnight
        if time >= open_hour or time < close_hour:
            return True
    else:
        # Normal hours
        if open_hour <= time < close_hour:
            return True
    
    return False


def calculate_wait_time(bar_name: str, arrival_time: float, group_size: int, is_game_day: bool) -> int:
    """Calculate expected wait time. All inputs handled safely."""
    # Safe conversions
    arrival_time = safe_float(arrival_time, 21.0)
    group_size = safe_int(group_size, 2)
    is_game_day = bool(is_game_day) if is_game_day is not None else False
    
    if bar_name not in BAR_ROSTER:
        return 10  # Default wait for unknown bar
    
    bar = BAR_ROSTER[bar_name]
    base_wait = safe_int(bar.get("base_wait", 10), 10)
    popularity = safe_int(bar.get("popularity", 3), 3)
    
    # Get hour for traffic lookup (handle midnight crossover)
    hour = int(arrival_time) % 24
    traffic_mult = HOURLY_TRAFFIC.get(hour, 1.5)
    
    # Calculate wait
    wait = base_wait * traffic_mult
    
    # Popularity factor
    wait *= (1 + (popularity - 3) * 0.15)
    
    # Group size factor (larger groups wait longer)
    if group_size > 2:
        wait *= (1 + (group_size - 2) * 0.08)
    
    # Game day factor
    if is_game_day:
        wait *= GAME_DAY_MULTIPLIER
    
    return max(1, int(round(wait)))


def simulate_route(route: List[str], start_time: float, group_size: int, is_game_day: bool) -> Dict:
    """Simulate a route through bars. All inputs handled safely."""
    # Safe conversions at entry point
    start_time = safe_float(start_time, 21.0)
    group_size = safe_int(group_size, 2)
    is_game_day = bool(is_game_day) if is_game_day is not None else False
    
    if not route:
        return {"feasible": False, "reason": "Empty route", "total_wait": 0, "steps": []}
    
    steps = []
    current_time = start_time
    total_wait = 0
    
    for i, bar in enumerate(route):
        # Check if bar exists
        if bar not in BAR_ROSTER:
            return {"feasible": False, "reason": f"Unknown bar: {bar}", "total_wait": 0, "steps": []}
        
        # Add travel time (except for first bar)
        if i > 0:
            current_time += TRAVEL_TIME / 60.0
        
        # Check if bar is open
        if not is_bar_open(bar, current_time):
            return {"feasible": False, "reason": f"{bar} is closed at {format_time(current_time)}", 
                    "total_wait": total_wait, "steps": steps}
        
        # Calculate wait
        wait = calculate_wait_time(bar, current_time, group_size, is_game_day)
        total_wait += wait
        
        # Record this stop
        arrival = current_time
        departure = current_time + (wait / 60.0) + (STAY_DURATION / 60.0)
        
        steps.append({
            "bar": bar,
            "arrival": arrival,
            "departure": departure,
            "wait": wait
        })
        
        current_time = departure
    
    return {
        "feasible": True,
        "total_wait": total_wait,
        "steps": steps,
        "end_time": current_time
    }


def optimize_route(bars: List[str], start_time: float, group_size: int, is_game_day: bool) -> Tuple[Optional[List[str]], Optional[Dict]]:
    """Find the optimal ordering of bars. All inputs handled safely."""
    # Safe conversions
    start_time = safe_float(start_time, 21.0)
    group_size = safe_int(group_size, 2)
    is_game_day = bool(is_game_day) if is_game_day is not None else False
    
    if not bars:
        return None, None
    
    # Filter to valid bars only
    valid_bars = [b for b in bars if b in BAR_ROSTER]
    if not valid_bars:
        return None, None
    
    # Limit to 5 bars for performance
    if len(valid_bars) > 5:
        valid_bars = valid_bars[:5]
    
    best_route = None
    best_result = None
    best_wait = float('inf')
    
    # Try all permutations
    for perm in permutations(valid_bars):
        route = list(perm)
        result = simulate_route(route, start_time, group_size, is_game_day)
        
        if result["feasible"] and result["total_wait"] < best_wait:
            best_wait = result["total_wait"]
            best_route = route
            best_result = result
    
    # If no feasible route found, return first permutation's result for error info
    if best_route is None:
        first_result = simulate_route(valid_bars, start_time, group_size, is_game_day)
        return None, first_result
    
    return best_route, best_result


def get_all_bars() -> List[Dict]:
    """Get list of all bars with their info."""
    return [
        {
            "name": name,
            "capacity": data["capacity"],
            "popularity": data["popularity"],
            "base_wait": data["base_wait"]
        }
        for name, data in BAR_ROSTER.items()
    ]


def get_bar_info(bar_name: str) -> Optional[Dict]:
    """Get info for a specific bar."""
    if bar_name not in BAR_ROSTER:
        return None
    
    data = BAR_ROSTER[bar_name]
    return {
        "name": bar_name,
        "capacity": data["capacity"],
        "popularity": data["popularity"],
        "base_wait": data["base_wait"],
        "hours": data["hours"]
    }
