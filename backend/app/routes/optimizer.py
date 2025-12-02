# =============================================================================
# backend/app/routes/optimizer.py
# =============================================================================
# This file defines all the API endpoints for the bar hopping optimizer.
# It's the "controller" layer that receives HTTP requests, coordinates
# between services (NLU, simulation, LLM), and returns responses.
#
# The main endpoint is POST /api/optimize which:
# 1. Parses the user's natural language request (NLU service)
# 2. Calculates the optimal route (simulation service)
# 3. Generates a friendly response (model service / LLM)
# =============================================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

# Import our service modules
from app.services.nlu import parse_user_request
from app.services.simulation import optimize_route, get_all_bars, get_bar_info
from app.services.model import (
    generate_response,
    generate_fallback_response,
    check_model_health,
    MODEL_BACKEND
)

# Set up logging so we can see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the router - this groups all our endpoints together
router = APIRouter()


# =============================================================================
# Pydantic Models for Request/Response Validation
# =============================================================================
# Pydantic models define the structure of data going in and out of our API.
# FastAPI uses these to automatically validate requests and generate docs.
# If a request doesn't match the model, FastAPI returns a clear error.

class RouteRequest(BaseModel):
    """
    The request body for the /optimize endpoint.
    
    Attributes:
        message: Natural language request like "let's hit chimys at 9pm"
        group_size: Number of people (optional, default 2)
        use_llm: Whether to use the LLM for response generation
    """
    message: str = Field(
        ...,  # ... means this field is required
        description="Natural language request describing the bar hopping plan",
        example="yo let's hit chimys and crickets at 9pm"
    )
    group_size: Optional[int] = Field(
        default=2,
        ge=1,   # Must be >= 1
        le=20,  # Must be <= 20
        description="Number of people in the group"
    )
    use_llm: bool = Field(
        default=True,
        description="Whether to use the LLM for natural response generation"
    )


class StopInfo(BaseModel):
    """Information about a single stop in the itinerary."""
    venue_name: str = Field(description="Name of the bar")
    arrival_time: str = Field(description="When to arrive (HH:MM format)")
    departure_time: str = Field(description="When to leave (HH:MM format)")
    expected_wait: int = Field(description="Expected wait time in minutes")


class ParsedInfo(BaseModel):
    """What the NLU extracted from the user's request."""
    bars: List[str] = Field(description="Bars identified in the request")
    start_time: Optional[float] = Field(description="Start time as decimal hours")
    group_size: int = Field(description="Number of people")
    is_game_day: bool = Field(description="Whether it's a game day")


class RouteResponse(BaseModel):
    """
    The response from the /optimize endpoint.
    Contains the optimized itinerary and a natural language message.
    """
    status: str = Field(
        description="'success', 'infeasible', or 'error'"
    )
    itinerary: List[StopInfo] = Field(
        default=[],
        description="Ordered list of stops"
    )
    total_wait_time: int = Field(
        default=0,
        description="Total wait time in minutes"
    )
    message: str = Field(
        description="Human-readable response message"
    )
    parsed_info: Optional[ParsedInfo] = Field(
        default=None,
        description="What was extracted from the request"
    )
    llm_used: bool = Field(
        default=False,
        description="Whether the LLM generated the message"
    )


class BarInfo(BaseModel):
    """Information about a single bar."""
    name: str
    capacity: int
    popularity: int
    base_wait: int


class BarsListResponse(BaseModel):
    """Response containing all available bars."""
    bars: List[BarInfo]
    count: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/optimize", response_model=RouteResponse)
async def optimize_bar_route(request: RouteRequest):
    """
    Process a natural language request and return an optimized bar route.
    
    This is the main endpoint of the application. It:
    1. Parses the natural language input using NLU
    2. Optimizes the route using simulation
    3. Generates a friendly response using the LLM (if available)
    
    Example requests:
    - "yo let's hit chimys and crickets at 9pm"
    - "plan a route for Bier Haus, Atomic, and Bar PM at 8"
    - "me and 5 friends need bars for game day at 7:30pm"
    """
    try:
        # =====================================================================
        # Step 1: Parse the natural language request
        # =====================================================================
        # The NLU service extracts structured data from casual language.
        # It handles typos, nicknames, and various phrasings.
        
        logger.info(f"Processing request: {request.message}")
        parsed = parse_user_request(request.message)
        
        # Create the parsed info for the response
        parsed_info = ParsedInfo(
            bars=parsed.get("bars", []),
            start_time=parsed.get("start_time"),
            group_size=parsed.get("group_size", 2),
            is_game_day=parsed.get("is_game_day", False)
        )
        
        logger.info(f"Parsed: bars={parsed['bars']}, time={parsed.get('start_time')}")
        
        # Check if we found any bars
        if not parsed["bars"]:
            # No bars found - return helpful error message
            llm_message = None
            if request.use_llm:
                llm_message = await generate_response(
                    user_message=request.message,
                    route_info={"feasible": False, "reason": "No bars identified"},
                    parsed_info=parsed
                )
            
            return RouteResponse(
                status="error",
                itinerary=[],
                total_wait_time=0,
                message=llm_message or (
                    "I couldn't identify any bars in your request. "
                    "Try mentioning specific bars like Chimy's, Cricket's, "
                    "Bier Haus, or Atomic!"
                ),
                parsed_info=parsed_info,
                llm_used=llm_message is not None
            )
        
        # =====================================================================
        # Step 2: Run the route optimization
        # =====================================================================
        # The simulation service calculates wait times and finds the optimal
        # order to visit the bars.
        
        group_size = request.group_size or parsed.get("group_size", 2)
        start_time = parsed.get("start_time", 21.0)  # Default 9 PM
        is_game_day = parsed.get("is_game_day", False)
        
        best_route, result = optimize_route(
            bars=parsed["bars"],
            start_hour=start_time,
            group_size=group_size,
            is_game_day=is_game_day
        )
        
        # =====================================================================
        # Step 3: Generate response message
        # =====================================================================
        # Use the LLM if available, otherwise fall back to rule-based response
        
        llm_used = False
        message = None
        
        if not result or not result.get("feasible"):
            # Route infeasible - generate helpful explanation
            route_info_for_llm = {
                "feasible": False,
                "reason": result.get("reason", "Unknown") if result else "No route",
                "total_wait": 0,
                "steps": []
            }
            
            if request.use_llm:
                message = await generate_response(
                    user_message=request.message,
                    route_info=route_info_for_llm,
                    parsed_info=parsed
                )
                llm_used = message is not None
            
            if not message:
                message = generate_fallback_response(route_info_for_llm, parsed)
            
            return RouteResponse(
                status="infeasible",
                itinerary=[],
                total_wait_time=0,
                message=message,
                parsed_info=parsed_info,
                llm_used=llm_used
            )
        
        # Route is feasible - format the itinerary
        itinerary = []
        for step in result.get("steps", []):
            itinerary.append(StopInfo(
                venue_name=step["bar"],
                arrival_time=step["arrival"],
                departure_time=step["depart"],
                expected_wait=step["wait"]
            ))
        
        # Generate natural language response
        route_info_for_llm = {
            "feasible": True,
            "total_wait": result.get("total_wait", 0),
            "steps": result.get("steps", []),
            "reason": None
        }
        
        if request.use_llm:
            message = await generate_response(
                user_message=request.message,
                route_info=route_info_for_llm,
                parsed_info=parsed
            )
            llm_used = message is not None
        
        if not message:
            message = generate_fallback_response(route_info_for_llm, parsed)
        
        logger.info(f"Returning route with {len(itinerary)} stops, LLM={llm_used}")
        
        return RouteResponse(
            status="success",
            itinerary=itinerary,
            total_wait_time=result.get("total_wait", 0),
            message=message,
            parsed_info=parsed_info,
            llm_used=llm_used
        )
        
    except Exception as e:
        logger.error(f"Error in optimize endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/bars", response_model=BarsListResponse)
async def list_bars():
    """
    Get a list of all available bars with their information.
    Useful for showing users what options are available.
    """
    try:
        bars_data = get_all_bars()
        bars_list = [
            BarInfo(
                name=bar["name"],
                capacity=bar.get("capacity", 100),
                popularity=bar.get("popularity", 3),
                base_wait=bar.get("base_wait", 10)
            )
            for bar in bars_data
        ]
        
        return BarsListResponse(
            bars=bars_list,
            count=len(bars_list)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bars/{bar_name}")
async def get_single_bar(bar_name: str):
    """Get detailed information about a specific bar."""
    try:
        bar_info = get_bar_info(bar_name)
        
        if not bar_info:
            raise HTTPException(
                status_code=404,
                detail=f"Bar '{bar_name}' not found"
            )
        
        return bar_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/health")
async def model_health():
    """
    Check the health and availability of the LLM service.
    
    Returns information about:
    - Which model backend is configured
    - Whether the model is available
    - GPU availability
    """
    try:
        status = await check_model_health()
        return {
            "status": "healthy" if status["available"] else "degraded",
            "model": {
                "backend": status["backend"],
                "available": status["available"],
                "message": status["message"]
            },
            "gpu": {
                "available": status.get("gpu_available", False),
                "name": status.get("gpu_name", None)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "model": {
                "backend": MODEL_BACKEND,
                "available": False,
                "message": str(e)
            },
            "gpu": {"available": False, "name": None}
        }
