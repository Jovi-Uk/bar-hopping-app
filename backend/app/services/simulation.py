# =============================================================================
# backend/app/services/simulation.py
# =============================================================================
# This service implements the route optimization engine. Given a list of bars
# to visit, it calculates the optimal order that minimizes total wait time.
#
# The simulation considers:
# - Time of day (bars get busier later in the evening)
# - Bar popularity (more popular bars have longer waits)
# - Group size (larger groups wait longer for tables)
# - Game day multiplier (Texas Tech games increase crowds)
# - Bar operating hours (can't visit a closed bar!)
#
# The optimization uses exhaustive search - it tries all possible orderings
# (permutations) of the bars and picks the one with the lowest total wait.
# For small numbers of bars (2-5), this is fast and gives the optimal answer.
# =============================================================================

from typing import Dict, List, Tuple, Optional, Any
from itertools import permutations
from datetime import datetime


# =============================================================================
# Configuration Constants
# =============================================================================
# These values control the simulation. They're defined as constants at the top
# so they can be easily adjusted without digging through the code.

BASE_WAIT_MULTIPLIER = 1.0      # Base multiplier for all wait times
POPULARITY_FACTOR = 0.08        # How much popularity affects wait per hour
GROUP_SIZE_PENALTY = 0.05       # Extra wait per person above 2
GAME_DAY_MULTIPLIER = 1.5       # Wait multiplier on game days

TRAVEL_TIME_MINUTES = 7         # Average walk time between bars
STAY_DURATION_MINUTES = 60      # How long to spend at each bar
MAX_BARS_IN_ROUTE = 5           # Maximum bars to optimize (keeps it fast)

MIN_START_HOUR = 17             # Earliest valid start (5 PM)
MAX_START_HOUR = 23             # Latest valid start (11 PM)


# =============================================================================
# Bar Data
# =============================================================================
# This dictionary contains all the information about each bar. In a production
# app, this would come from a database, but for simplicity we define it here.
#
# Each bar has:
# - capacity: Maximum occupancy
# - popularity: 1-5 scale (5 = most popular, longest waits)
# - base_wait: Base wait time in minutes at a normal hour
# - hours: Operating hours by day of week (open_hour, close_hour)

BAR_ROSTER = {
    "Chimy's": {
        "name": "Chimy's",
        "capacity": 200,
        "popularity": 4,
        "base_wait": 15,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": (18, 0)
        }
    },
    "Cricket's": {
        "name": "Cricket's",
        "capacity": 180,
        "popularity": 4,
        "base_wait": 12,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": (18, 0)
        }
    },
    "Bier Haus": {
        "name": "Bier Haus",
        "capacity": 150,
        "popularity": 3,
        "base_wait": 10,
        "hours": {
            "monday": (16, 2),
            "tuesday": (16, 2),
            "wednesday": (16, 2),
            "thursday": (16, 2),
            "friday": (15, 2),
            "saturday": (15, 2),
            "sunday": (17, 0)
        }
    },
    "Atomic": {
        "name": "Atomic",
        "capacity": 120,
        "popularity": 4,
        "base_wait": 8,
        "hours": {
            "monday": (18, 2),
            "tuesday": (18, 2),
            "wednesday": (18, 2),
            "thursday": (18, 2),
            "friday": (17, 2),
            "saturday": (17, 2),
            "sunday": (19, 0)
        }
    },
    "Bar PM": {
        "name": "Bar PM",
        "capacity": 100,
        "popularity": 3,
        "base_wait": 8,
        "hours": {
            "monday": (19, 2),
            "tuesday": (19, 2),
            "wednesday": (19, 2),
            "thursday": (19, 2),
            "friday": (18, 2),
            "saturday": (18, 2),
            "sunday": None  # Closed
        }
    },
    "Misquetes": {
        "name": "Misquetes",
        "capacity": 140,
        "popularity": 3,
        "base_wait": 10,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": (18, 0)
        }
    },
    "Wrecked": {
        "name": "Wrecked",
        "capacity": 160,
        "popularity": 3,
        "base_wait": 10,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": (18, 0)
        }
    },
    "The Library": {
        "name": "The Library",
        "capacity": 130,
        "popularity": 3,
        "base_wait": 8,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": None
        }
    },
    "Bash's": {
        "name": "Bash's",
        "capacity": 170,
        "popularity": 4,
        "base_wait": 12,
        "hours": {
            "monday": (17, 2),
            "tuesday": (17, 2),
            "wednesday": (17, 2),
            "thursday": (17, 2),
            "friday": (16, 2),
            "saturday": (16, 2),
            "sunday": (18, 0)
        }
    },
    "Electric Avenue": {
        "name": "Electric Avenue",
        "capacity": 200,
        "popularity": 4,
        "base_wait": 15,
        "hours": {
            "monday": (18, 2),
            "tuesday": (18, 2),
            "wednesday": (18, 2),
            "thursday": (18, 2),
            "friday": (17, 2),
            "saturday": (17, 2),
            "sunday": None
        }
    }
}


def get_day_of_week() -> str:
    """Get current day of the week as lowercase string."""
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return days[datetime.now().weekday()]


def format_time(hour_float: float) -> str:
    """
    Convert decimal hours to HH:MM string.
    
    Args:
        hour_float: Time as decimal (21.5 = 9:30 PM)
    
    Returns:
        Time string in 24-hour format ("21:30")
    """
    hour_float = hour_float % 24  # Handle times past midnight
    hours = int(hour_float)
    minutes = int((hour_float - hours) * 60)
    return f"{hours:02d}:{minutes:02d}"


def is_bar_open(bar_name: str, hour: float, day: str = None) -> bool:
    """
    Check if a bar is open at a given time.
    
    Args:
        bar_name: The canonical name of the bar
        hour: Time as decimal hours (0-24)
        day: Day of week (lowercase), defaults to today
    
    Returns:
        True if the bar is open, False otherwise
    """
    if bar_name not in BAR_ROSTER:
        return False
    
    bar = BAR_ROSTER[bar_name]
    day = day or get_day_of_week()
    hours = bar["hours"].get(day)
    
    if hours is None:
        return False  # Closed that day
    
    open_hour, close_hour = hours
    
    # Handle bars that close after midnight
    if close_hour < open_hour:
        # Open if after opening OR before closing (next day)
        return hour >= open_hour or hour < close_hour
    else:
        return open_hour <= hour < close_hour


def calculate_wait_time(
    bar_name: str,
    arrival_hour: float,
    group_size: int,
    is_game_day: bool
) -> int:
    """
    Calculate expected wait time at a bar.
    
    The formula considers:
    1. Base wait time (from bar data)
    2. Time of day factor (busier later)
    3. Popularity factor (popular bars = longer waits)
    4. Group size penalty (larger groups wait longer)
    5. Game day multiplier (special events)
    
    Args:
        bar_name: The canonical name of the bar
        arrival_hour: When you'll arrive (decimal hours)
        group_size: Number of people
        is_game_day: Whether it's a game day
    
    Returns:
        Expected wait time in minutes
    """
    if bar_name not in BAR_ROSTER:
        return 15  # Default for unknown bars
    
    bar = BAR_ROSTER[bar_name]
    
    # Start with base wait
    wait = bar["base_wait"] * BASE_WAIT_MULTIPLIER
    
    # Time of day factor (bars get busier later)
    if arrival_hour >= 22:
        time_factor = 1.4  # Peak hours (10 PM+)
    elif arrival_hour >= 21:
        time_factor = 1.2  # Getting busy (9-10 PM)
    elif arrival_hour >= 20:
        time_factor = 1.1  # Warming up (8-9 PM)
    else:
        time_factor = 1.0  # Early evening
    
    wait *= time_factor
    
    # Popularity factor
    popularity_multiplier = 1 + (bar["popularity"] - 3) * POPULARITY_FACTOR
    wait *= popularity_multiplier
    
    # Group size penalty
    group_penalty = 1 + max(0, group_size - 2) * GROUP_SIZE_PENALTY
    wait *= group_penalty
    
    # Game day multiplier
    if is_game_day:
        wait *= GAME_DAY_MULTIPLIER
    
    return int(round(wait))


def simulate_route(
    route: List[str],
    start_hour: float,
    group_size: int,
    is_game_day: bool
) -> Dict[str, Any]:
    """
    Simulate a complete bar hopping route.
    
    Walks through each bar in order, calculating arrival times, wait times,
    and departure times. Checks if each bar is open when we'd arrive.
    
    Args:
        route: Ordered list of bar names
        start_hour: When to start (decimal hours)
        group_size: Number of people
        is_game_day: Whether it's a game day
    
    Returns:
        Dictionary with:
        - feasible: Whether the route is possible
        - total_wait: Sum of all wait times
        - steps: Detailed info for each stop
        - reason: Explanation if infeasible
    """
    current_hour = start_hour
    total_wait = 0
    steps = []
    day = get_day_of_week()
    
    for i, bar_name in enumerate(route):
        # Check if bar exists
        if bar_name not in BAR_ROSTER:
            return {
                "feasible": False,
                "reason": f"Unknown bar: {bar_name}",
                "total_wait": 0,
                "steps": []
            }
        
        # Check if bar is open
        if not is_bar_open(bar_name, current_hour, day):
            return {
                "feasible": False,
                "reason": f"{bar_name} is closed at {format_time(current_hour)}",
                "total_wait": 0,
                "steps": []
            }
        
        # Calculate wait time
        wait = calculate_wait_time(bar_name, current_hour, group_size, is_game_day)
        total_wait += wait
        
        # Record this stop
        arrival_time = format_time(current_hour)
        departure_hour = current_hour + (wait / 60) + (STAY_DURATION_MINUTES / 60)
        departure_time = format_time(departure_hour)
        
        steps.append({
            "bar": bar_name,
            "arrival": arrival_time,
            "depart": departure_time,
            "wait": wait
        })
        
        # Move to next bar (add travel time)
        if i < len(route) - 1:
            current_hour = departure_hour + (TRAVEL_TIME_MINUTES / 60)
    
    return {
        "feasible": True,
        "total_wait": total_wait,
        "steps": steps,
        "reason": None
    }


def optimize_route(
    bars: List[str],
    start_hour: float,
    group_size: int = 2,
    is_game_day: bool = False
) -> Tuple[Optional[List[str]], Optional[Dict[str, Any]]]:
    """
    Find the optimal order to visit a set of bars.
    
    Uses exhaustive search to try all possible orderings and returns the
    one with the lowest total wait time. This is fast for small numbers
    of bars (2-5) which is the typical use case.
    
    Args:
        bars: List of bar names to visit
        start_hour: When to start (decimal hours, e.g., 21.0 = 9 PM)
        group_size: Number of people
        is_game_day: Whether it's a game day
    
    Returns:
        Tuple of (best_route, result_dict):
        - best_route: Optimal ordering of bars, or None if infeasible
        - result_dict: Simulation results with wait times and steps
    """
    if not bars:
        return None, {"feasible": False, "reason": "No bars specified", "total_wait": 0, "steps": []}
    
    # Filter to known bars only
    valid_bars = [b for b in bars if b in BAR_ROSTER]
    if not valid_bars:
        return None, {"feasible": False, "reason": "No recognized bars", "total_wait": 0, "steps": []}
    
    # Limit number of bars for performance
    if len(valid_bars) > MAX_BARS_IN_ROUTE:
        valid_bars = valid_bars[:MAX_BARS_IN_ROUTE]
    
    # If only one bar, no optimization needed
    if len(valid_bars) == 1:
        result = simulate_route(valid_bars, start_hour, group_size, is_game_day)
        if result["feasible"]:
            return valid_bars, result
        else:
            return None, result
    
    # Try all permutations
    best_route = None
    best_result = None
    best_wait = float('inf')
    
    for perm in permutations(valid_bars):
        route = list(perm)
        result = simulate_route(route, start_hour, group_size, is_game_day)
        
        if result["feasible"] and result["total_wait"] < best_wait:
            best_wait = result["total_wait"]
            best_route = route
            best_result = result
    
    if best_route:
        return best_route, best_result
    
    # No feasible route - figure out why
    problematic = []
    for bar in valid_bars:
        test = simulate_route([bar], start_hour, group_size, is_game_day)
        if not test["feasible"]:
            problematic.append(bar)
    
    if problematic:
        reason = f"These bars are closed at that time: {', '.join(problematic)}"
    else:
        reason = "No feasible route found"
    
    return None, {"feasible": False, "reason": reason, "total_wait": 0, "steps": []}


def get_all_bars() -> List[Dict[str, Any]]:
    """Get a list of all bars with their basic info."""
    return [
        {
            "name": bar["name"],
            "capacity": bar["capacity"],
            "popularity": bar["popularity"],
            "base_wait": bar["base_wait"]
        }
        for bar in BAR_ROSTER.values()
    ]


def get_bar_info(bar_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed info about a specific bar."""
    # Try exact match
    if bar_name in BAR_ROSTER:
        bar = BAR_ROSTER[bar_name]
        return {
            "name": bar["name"],
            "capacity": bar["capacity"],
            "popularity": bar["popularity"],
            "base_wait": bar["base_wait"],
            "hours": bar["hours"],
            "is_open_now": is_bar_open(bar_name, 21.0)
        }
    
    # Try case-insensitive
    for name, bar in BAR_ROSTER.items():
        if name.lower() == bar_name.lower():
            return {
                "name": bar["name"],
                "capacity": bar["capacity"],
                "popularity": bar["popularity"],
                "base_wait": bar["base_wait"],
                "hours": bar["hours"],
                "is_open_now": is_bar_open(name, 21.0)
            }
    
    return None
