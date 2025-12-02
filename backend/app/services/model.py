# =============================================================================
# backend/app/services/model.py
# =============================================================================
# This service handles all interaction with the fine-tuned LLM (Language Model).
# The model generates natural, conversational responses based on the route
# optimization results.
#
# The service supports multiple backends:
# - "local": Load the model directly on this server (requires GPU)
# - "huggingface": Use HuggingFace Inference Endpoints API
# - "disabled": No LLM, use rule-based responses only
#
# This flexibility allows the app to work in different deployment scenarios,
# from local development (disabled) to production (local with GPU).
# =============================================================================

import os
import json
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration from Environment Variables
# =============================================================================
# These values are set in the .env file locally, and in Railway's environment
# variables in production.

MODEL_BACKEND = os.environ.get("MODEL_BACKEND", "disabled").lower()
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "microsoft/Phi-3.5-mini-instruct")
HF_LORA_ID = os.environ.get("HF_LORA_ID", "")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_INFERENCE_URL = os.environ.get("HF_INFERENCE_URL", "")

# Model generation parameters
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.7
TOP_P = 0.9

# Global model instance (for local loading - loaded once, reused for all requests)
_model = None
_tokenizer = None
_model_loaded = False


# =============================================================================
# System Prompt
# =============================================================================
# This prompt defines the model's personality and response style. It was used
# during fine-tuning to ensure consistent, helpful responses.

SYSTEM_PROMPT = """You are a friendly bar hopping assistant for Lubbock, Texas. Your job is to help users plan their night out by providing optimized bar routes.

When given a route with bar information, respond in a conversational, friendly tone. Include:
1. A warm greeting or acknowledgment
2. The optimized route as a clear itinerary
3. Total expected wait time
4. Any helpful tips based on the time, group size, or game day status

Format times in 12-hour format (9:30 PM, not 21:30).
Keep responses concise but friendly.
Use emojis sparingly to add personality (🍺, 🎉, ⏰).

If the route is infeasible, explain why in a helpful way and suggest alternatives."""


# =============================================================================
# Local Model Loading
# =============================================================================
# These functions handle loading and running the model locally. This requires
# a GPU with at least 8GB of VRAM.

def load_model_local():
    """
    Load the fine-tuned Phi-3.5 model locally with LoRA adapters.
    
    Uses 4-bit quantization to reduce memory usage, making it possible to run
    on smaller GPUs. The model is loaded once and cached for subsequent requests.
    
    Returns:
        Tuple of (model, tokenizer) or (None, None) if loading fails
    """
    global _model, _tokenizer, _model_loaded
    
    # Return cached model if already loaded
    if _model_loaded:
        return _model, _tokenizer
    
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
        
        logger.info(f"Loading model: {HF_MODEL_ID}")
        
        # Check for GPU
        if not torch.cuda.is_available():
            logger.warning("No GPU available - model loading may fail or be very slow")
        else:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        
        # Configure 4-bit quantization for memory efficiency
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        
        # Load tokenizer
        _tokenizer = AutoTokenizer.from_pretrained(
            HF_MODEL_ID,
            trust_remote_code=True
        )
        _tokenizer.pad_token = _tokenizer.eos_token
        _tokenizer.padding_side = "right"
        
        # Load base model with quantization
        logger.info("Loading base model with 4-bit quantization...")
        base_model = AutoModelForCausalLM.from_pretrained(
            HF_MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        
        # Load LoRA adapters if specified
        if HF_LORA_ID:
            logger.info(f"Loading LoRA adapters from: {HF_LORA_ID}")
            _model = PeftModel.from_pretrained(base_model, HF_LORA_ID)
        else:
            logger.info("No LoRA adapters specified, using base model")
            _model = base_model
        
        _model.eval()
        _model_loaded = True
        logger.info("✓ Model loaded successfully!")
        
        return _model, _tokenizer
        
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        _model = None
        _tokenizer = None
        _model_loaded = False
        return None, None


def generate_local(prompt: str) -> Optional[str]:
    """
    Generate a response using the locally loaded model.
    
    Args:
        prompt: The formatted prompt including system message
    
    Returns:
        Generated text, or None if generation fails
    """
    import torch
    
    model, tokenizer = load_model_local()
    
    if model is None or tokenizer is None:
        return None
    
    try:
        # Tokenize the prompt
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024
        ).to(model.device)
        
        input_length = inputs['input_ids'].shape[1]
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        
        # Decode only the new tokens (not the input)
        response = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        ).strip()
        
        return response
        
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        return None


# =============================================================================
# HuggingFace Inference API
# =============================================================================

async def generate_huggingface(prompt: str) -> Optional[str]:
    """
    Generate using HuggingFace Inference Endpoints API.
    
    This is useful if you want to run the model on HuggingFace's infrastructure
    instead of managing your own GPU server.
    
    Args:
        prompt: The formatted prompt
    
    Returns:
        Generated text, or None if request fails
    """
    import httpx
    
    if not HF_INFERENCE_URL or not HF_API_TOKEN:
        logger.warning("HF Inference not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": MAX_NEW_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "do_sample": True,
            "return_full_text": False
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                HF_INFERENCE_URL,
                headers=headers,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
            return None
            
    except Exception as e:
        logger.error(f"HF Inference error: {str(e)}")
        return None


# =============================================================================
# Prompt Formatting
# =============================================================================

def format_prompt(
    user_message: str,
    route_info: Optional[Dict[str, Any]] = None,
    parsed_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format a prompt for the model with route context.
    
    Creates a structured prompt that includes the system message, route
    optimization results, and the user's original request.
    
    Args:
        user_message: The user's original request
        route_info: Results from route optimization
        parsed_info: What NLU extracted from the request
    
    Returns:
        Formatted prompt ready for the model
    """
    # Build context about the route
    context_parts = []
    
    if route_info:
        if route_info.get("feasible"):
            context_parts.append("Route optimization successful!")
            context_parts.append(f"Total wait time: {route_info.get('total_wait', 0)} minutes")
            
            steps = route_info.get("steps", [])
            if steps:
                context_parts.append("\nItinerary:")
                for i, step in enumerate(steps, 1):
                    context_parts.append(
                        f"{i}. {step['bar']}: Arrive {step['arrival']}, "
                        f"Leave {step['depart']} (wait: {step['wait']} min)"
                    )
        else:
            context_parts.append(f"Route not feasible: {route_info.get('reason', 'Unknown')}")
    
    if parsed_info:
        context_parts.append(f"\nBars requested: {', '.join(parsed_info.get('bars', []))}")
        if parsed_info.get('start_time'):
            context_parts.append(f"Start time: {parsed_info['start_time']}")
        context_parts.append(f"Group size: {parsed_info.get('group_size', 2)}")
        if parsed_info.get('is_game_day'):
            context_parts.append("Game day: Yes")
    
    context = "\n".join(context_parts) if context_parts else ""
    
    # Format using Phi-3.5's chat template
    prompt = f"""<|system|>
{SYSTEM_PROMPT}<|end|>
<|user|>
User request: {user_message}

{context}<|end|>
<|assistant|>
"""
    
    return prompt


# =============================================================================
# Main Generation Function
# =============================================================================

async def generate_response(
    user_message: str,
    route_info: Optional[Dict[str, Any]] = None,
    parsed_info: Optional[Dict[str, Any]] = None,
    use_direct_inference: bool = False
) -> Optional[str]:
    """
    Generate a response using the configured model backend.
    
    This is the main entry point for LLM generation. It formats the prompt
    and routes to the appropriate backend (local, HuggingFace, or disabled).
    
    Args:
        user_message: The user's original request
        route_info: Results from route optimization
        parsed_info: What NLU extracted
        use_direct_inference: If True, let model generate route directly
    
    Returns:
        Generated response string, or None if unavailable
    """
    # Format the prompt
    prompt = format_prompt(user_message, route_info, parsed_info)
    
    logger.info(f"Generating response with backend: {MODEL_BACKEND}")
    
    # Route to appropriate backend
    if MODEL_BACKEND == "local":
        # Local generation is synchronous, run in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, generate_local, prompt)
    
    elif MODEL_BACKEND == "huggingface":
        return await generate_huggingface(prompt)
    
    else:
        logger.info("Model backend disabled, using fallback")
        return None


# =============================================================================
# Fallback Response Generation
# =============================================================================

def generate_fallback_response(
    route_info: Dict[str, Any],
    parsed_info: Dict[str, Any]
) -> str:
    """
    Generate a rule-based response when the LLM is unavailable.
    
    This ensures the app always provides useful output, even without
    GPU access or when the model service is down.
    
    Args:
        route_info: Results from route optimization
        parsed_info: What NLU extracted
    
    Returns:
        Formatted response string
    """
    if not route_info.get("feasible"):
        reason = route_info.get("reason", "timing constraints")
        return (
            f"😅 I couldn't find a feasible route - {reason}. "
            f"Try adjusting your start time or picking different bars!"
        )
    
    steps = route_info.get("steps", [])
    total_wait = route_info.get("total_wait", 0)
    
    if not steps:
        return "I found a route but couldn't format it. Please try again!"
    
    # Build the response
    lines = ["🍺 Here's your optimized bar hopping route!\n"]
    
    for i, step in enumerate(steps, 1):
        # Convert 24h to 12h
        def to_12h(time_str):
            h, m = map(int, time_str.split(':'))
            period = "PM" if h >= 12 else "AM"
            h = h % 12 or 12
            return f"{h}:{m:02d} {period}"
        
        lines.append(
            f"**{i}. {step['bar']}**\n"
            f"   Arrive: {to_12h(step['arrival'])} → Leave: {to_12h(step['depart'])}\n"
            f"   Expected wait: ~{step['wait']} min\n"
        )
    
    # Summary
    if total_wait < 30:
        wait_comment = "Minimal waiting tonight! 🎉"
    elif total_wait < 60:
        wait_comment = "Pretty reasonable wait times!"
    else:
        wait_comment = "Some waiting, but worth it!"
    
    lines.append(f"\n**Total wait: {total_wait} min** - {wait_comment}")
    
    if parsed_info.get("is_game_day"):
        lines.append("\n\n🏈 *Game day crowds factored in!*")
    
    return "\n".join(lines)


# =============================================================================
# Health Check
# =============================================================================

async def check_model_health() -> Dict[str, Any]:
    """
    Check the health/availability of the model service.
    
    Returns a status report for the /model/health endpoint.
    """
    status = {
        "backend": MODEL_BACKEND,
        "available": False,
        "message": "",
        "gpu_available": False
    }
    
    # Check GPU
    try:
        import torch
        status["gpu_available"] = torch.cuda.is_available()
        if status["gpu_available"]:
            status["gpu_name"] = torch.cuda.get_device_name(0)
    except:
        pass
    
    # Check model availability based on backend
    if MODEL_BACKEND == "local":
        if status["gpu_available"]:
            model, tokenizer = load_model_local()
            status["available"] = model is not None
            status["message"] = "Model loaded" if model else "Failed to load model"
        else:
            status["available"] = False
            status["message"] = "No GPU available for local inference"
    
    elif MODEL_BACKEND == "huggingface":
        status["available"] = bool(HF_INFERENCE_URL and HF_API_TOKEN)
        status["message"] = "HF configured" if status["available"] else "Missing HF config"
    
    else:
        status["available"] = False
        status["message"] = "Model backend disabled - using rule-based responses"
    
    return status
