# =============================================================================
# API Routes - BACKWARD COMPATIBLE (works with old AND new frontend)
# =============================================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import traceback

from ..services.nlu import parse_user_request, VALID_BARS
from ..services.simulation import (
    optimize_route, simulate_route, get_all_bars, get_bar_info,
    format_time, safe_float, safe_int
)
from ..services.model import generate_response, check_model_health

router = APIRouter()


# =============================================================================
# Request/Response Models - BACKWARD COMPATIBLE
# =============================================================================

class RouteRequest(BaseModel):
    message: str = Field(..., description="User's natural language request")
    group_size: Optional[int] = Field(default=2, description="Number of people")
    use_llm: Optional[bool] = Field(default=True, description="Use LLM for response")


class StopInfo(BaseModel):
    venue_name: str
    arrival_time: str
    departure_time: str
    expected_wait: int


class RouteResponse(BaseModel):
    # BOTH formats for compatibility
    success: bool
    status: str  # "success" or "error" - for old frontend
    message: str
    itinerary: List[StopInfo] = []
    total_wait_time: int = 0
    parsed_bars: List[str] = []
    parsed_time: str = ""
    is_game_day: bool = False
    llm_used: bool = False


class BarInfo(BaseModel):
    name: str
    capacity: int
    popularity: int
    base_wait: int


class BarsListResponse(BaseModel):
    bars: List[BarInfo]
    count: int


# =============================================================================
# Routes
# =============================================================================

@router.post("/optimize", response_model=RouteResponse)
async def optimize_bar_route(request: RouteRequest):
    """Main endpoint - parse request, optimize route, generate response."""
    try:
        if not request.message or not request.message.strip():
            return RouteResponse(
                success=False,
                status="error",
                message="Please tell me which bars you'd like to visit! For example: 'Let's hit Chimy's and Cricket's at 9pm'",
                itinerary=[],
                total_wait_time=0,
                parsed_bars=[],
                parsed_time="",
                is_game_day=False,
                llm_used=False
            )
        
        parsed = parse_user_request(request.message)
        bars = parsed.get("bars", [])
        start_time = safe_float(parsed.get("start_time"), 21.0)
        is_game_day = bool(parsed.get("is_game_day", False))
        
        if request.group_size is not None:
            group_size = safe_int(request.group_size, 2)
        else:
            group_size = safe_int(parsed.get("group_size"), 2)
        
        if not bars:
            return RouteResponse(
                success=False,
                status="error",
                message=f"I couldn't find any bar names in your request. Available bars: {', '.join(VALID_BARS)}. Try something like 'Chimy's and Cricket's at 9pm'",
                itinerary=[],
                total_wait_time=0,
                parsed_bars=[],
                parsed_time=format_time(start_time),
                is_game_day=is_game_day,
                llm_used=False
            )
        
        best_route, result = optimize_route(bars, start_time, group_size, is_game_day)
        
        if best_route is None or result is None or not result.get("feasible", False):
            reason = result.get("reason", "Route not feasible") if result else "Could not plan route"
            return RouteResponse(
                success=False,
                status="error",
                message=f"Couldn't plan that route: {reason}. Try an earlier time or different bars.",
                itinerary=[],
                total_wait_time=0,
                parsed_bars=bars,
                parsed_time=format_time(start_time),
                is_game_day=is_game_day,
                llm_used=False
            )
        
        itinerary = []
        for step in result.get("steps", []):
            arrival = safe_float(step.get("arrival"), 21.0)
            departure = safe_float(step.get("departure"), 22.0)
            wait = safe_int(step.get("wait"), 5)
            
            itinerary.append(StopInfo(
                venue_name=step.get("bar", "Unknown"),
                arrival_time=format_time(arrival),
                departure_time=format_time(departure),
                expected_wait=wait
            ))
        
        total_wait = safe_int(result.get("total_wait"), 0)
        
        llm_used = False
        if request.use_llm:
            try:
                llm_response = await generate_response(
                    user_message=request.message,
                    route=best_route,
                    result=result,
                    is_game_day=is_game_day
                )
                if llm_response and llm_response != "":
                    message = llm_response
                    llm_used = True
                else:
                    message = _generate_fallback_message(best_route, total_wait, is_game_day)
            except Exception as e:
                print(f"LLM error (using fallback): {e}")
                message = _generate_fallback_message(best_route, total_wait, is_game_day)
        else:
            message = _generate_fallback_message(best_route, total_wait, is_game_day)
        
        return RouteResponse(
            success=True,
            status="success",  # For old frontend compatibility
            message=message,
            itinerary=itinerary,
            total_wait_time=total_wait,
            parsed_bars=bars,
            parsed_time=format_time(start_time),
            is_game_day=is_game_day,
            llm_used=llm_used
        )
        
    except Exception as e:
        print(f"Error in optimize endpoint: {e}")
        traceback.print_exc()
        return RouteResponse(
            success=False,
            status="error",
            message=f"Something went wrong: {str(e)}. Please try a simpler request like 'Chimy's and Cricket's at 9pm'",
            itinerary=[],
            total_wait_time=0,
            parsed_bars=[],
            parsed_time="",
            is_game_day=False,
            llm_used=False
        )


def _generate_fallback_message(route: List[str], total_wait: int, is_game_day: bool) -> str:
    """Generate a simple response when LLM is unavailable."""
    if not route:
        return "I couldn't plan a route with those bars."
    
    route_str = " → ".join(route)
    game_day_note = " It's game day, so expect bigger crowds!" if is_game_day else ""
    
    return f"Here's your optimized route: {route_str}. Total expected wait: ~{total_wait} minutes.{game_day_note} Have fun! 🍺"


@router.get("/bars", response_model=BarsListResponse)
async def list_bars():
    """Get all available bars."""
    try:
        bars = get_all_bars()
        bar_list = [
            BarInfo(
                name=b["name"],
                capacity=b["capacity"],
                popularity=b["popularity"],
                base_wait=b["base_wait"]
            )
            for b in bars
        ]
        return BarsListResponse(bars=bar_list, count=len(bar_list))
    except Exception as e:
        print(f"Error listing bars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bars/{bar_name}")
async def get_single_bar(bar_name: str):
    """Get info for a specific bar."""
    try:
        bar = get_bar_info(bar_name)
        if not bar:
            raise HTTPException(status_code=404, detail=f"Bar '{bar_name}' not found")
        return bar
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting bar info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/health")
async def model_health():
    """
    Check if the LLM is available.
    Returns BOTH flat and nested format for frontend compatibility.
    """
    try:
        health = check_model_health()
        is_available = health.get("available", False)
        backend = health.get("backend", "unknown")
        gpu_available = health.get("gpu_available", False)
        gpu_name = health.get("gpu_name")
        msg = health.get("message", "Unknown status")
        
        # Return BOTH formats for compatibility
        return {
            # New flat format
            "status": "ok" if is_available else "degraded",
            "model_backend": backend,
            "model_available": is_available,
            "message": msg,
            "gpu_available": gpu_available,
            "gpu_name": gpu_name,
            # Old nested format for backward compatibility
            "model": {
                "backend": backend,
                "available": is_available,
                "message": msg
            },
            "gpu": {
                "available": gpu_available,
                "name": gpu_name
            }
        }
    except Exception as e:
        print(f"Error checking model health: {e}")
        return {
            "status": "error",
            "model_backend": "unknown",
            "model_available": False,
            "message": str(e),
            "gpu_available": False,
            "gpu_name": None,
            "model": {
                "backend": "unknown",
                "available": False,
                "message": str(e)
            },
            "gpu": {
                "available": False,
                "name": None
            }
        }
