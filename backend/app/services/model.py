# =============================================================================
# LLM Service (FIXED - Robust type handling and error handling)
# =============================================================================

import os
import logging
from typing import Optional, Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MODEL_BACKEND = os.environ.get("MODEL_BACKEND", "disabled").lower()
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "microsoft/Phi-3.5-mini-instruct")
HF_LORA_ID = os.environ.get("HF_LORA_ID", "")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")

MAX_NEW_TOKENS = 512
TEMPERATURE = 0.7

# Global model cache
_model = None
_tokenizer = None
_model_loaded = False

SYSTEM_PROMPT = """You are a friendly bar hopping assistant for Lubbock, Texas. Help users plan their night out with optimized bar routes. Be conversational, concise, and friendly. Use emojis sparingly."""


def safe_float(value, default: float = 21.0) -> float:
    """Safely convert to float."""
    if value is None:
        return default
    try:
        return float(value)
    except:
        return default


def safe_int(value, default: int = 0) -> int:
    """Safely convert to int."""
    if value is None:
        return default
    try:
        return int(value)
    except:
        return default


def format_time_12h(decimal_hour) -> str:
    """Convert decimal hour (float) to 12h format string."""
    decimal_hour = safe_float(decimal_hour, 21.0)
    
    if decimal_hour >= 24:
        decimal_hour -= 24
    
    hours = int(decimal_hour)
    minutes = int((decimal_hour - hours) * 60)
    
    period = "PM" if 12 <= hours < 24 else "AM"
    display_hour = hours % 12
    if display_hour == 0:
        display_hour = 12
    
    return f"{display_hour}:{minutes:02d} {period}"


def load_model_local():
    """Load the model locally with LoRA adapters."""
    global _model, _tokenizer, _model_loaded
    
    if _model_loaded:
        return _model, _tokenizer
    
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
        
        logger.info(f"Loading model: {HF_MODEL_ID}")
        
        if not torch.cuda.is_available():
            logger.warning("No GPU available")
            return None, None
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        
        tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            HF_MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        
        if HF_LORA_ID:
            logger.info(f"Loading LoRA adapters: {HF_LORA_ID}")
            model = PeftModel.from_pretrained(model, HF_LORA_ID)
        
        _model = model
        _tokenizer = tokenizer
        _model_loaded = True
        
        logger.info("Model loaded successfully!")
        return _model, _tokenizer
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None, None


def generate_local(prompt: str) -> str:
    """Generate response using local model."""
    model, tokenizer = load_model_local()
    
    if model is None or tokenizer is None:
        return ""
    
    try:
        import torch
        
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
            )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the assistant's response
        if "[/INST]" in response:
            response = response.split("[/INST]")[-1].strip()
        elif "assistant" in response.lower():
            parts = response.lower().split("assistant")
            if len(parts) > 1:
                response = parts[-1].strip()
        
        return response
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return ""


def build_prompt(user_message: str, route: List[str], result: Dict, is_game_day: bool) -> str:
    """Build the prompt for the LLM."""
    route_str = " → ".join(route) if route else "No route"
    total_wait = safe_int(result.get("total_wait"), 0)
    
    steps_text = ""
    for i, step in enumerate(result.get("steps", []), 1):
        bar = step.get("bar", "Unknown")
        arrival = format_time_12h(step.get("arrival"))
        departure = format_time_12h(step.get("departure", step.get("depart")))
        wait = safe_int(step.get("wait"), 5)
        steps_text += f"{i}. {bar}: arrive {arrival}, leave {departure}, wait ~{wait}min\n"
    
    context = f"""Route: {route_str}
Total wait: {total_wait} minutes
Game day: {'Yes' if is_game_day else 'No'}
Itinerary:
{steps_text}"""
    
    prompt = f"""<s>[INST] <<SYS>>
{SYSTEM_PROMPT}
<</SYS>>

User request: {user_message}

{context}

Provide a friendly, conversational response with the optimized route. [/INST]"""
    
    return prompt


async def generate_response(
    user_message: str,
    route: List[str],
    result: Dict,
    is_game_day: bool = False
) -> str:
    """Generate response using the configured backend."""
    try:
        if MODEL_BACKEND == "local":
            prompt = build_prompt(user_message, route, result, is_game_day)
            response = generate_local(prompt)
            if response:
                return response
        
        # Fallback to rule-based response
        return generate_fallback(route, result, is_game_day)
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return generate_fallback(route, result, is_game_day)


def generate_fallback(route: List[str], result: Dict, is_game_day: bool) -> str:
    """Generate a rule-based response when LLM is unavailable."""
    if not route:
        return "I couldn't plan a route. Please try different bars or times."
    
    if not result or not result.get("feasible", False):
        reason = result.get("reason", "timing constraints") if result else "unknown"
        return f"😅 Couldn't make that route work due to {reason}. Try an earlier time!"
    
    steps = result.get("steps", [])
    total_wait = safe_int(result.get("total_wait"), 0)
    
    lines = ["🍺 Here's your optimized route!\n"]
    
    for i, step in enumerate(steps, 1):
        bar = step.get("bar", "Unknown")
        arrival = format_time_12h(step.get("arrival"))
        departure = format_time_12h(step.get("departure", step.get("depart")))
        wait = safe_int(step.get("wait"), 5)
        
        lines.append(f"**{i}. {bar}**")
        lines.append(f"   Arrive: {arrival} → Leave: {departure}")
        lines.append(f"   Wait: ~{wait} min\n")
    
    if total_wait < 30:
        wait_note = "Minimal waiting tonight! 🎉"
    elif total_wait < 60:
        wait_note = "Pretty reasonable wait times!"
    else:
        wait_note = "Some waiting, but worth it!"
    
    lines.append(f"**Total wait: {total_wait} min** - {wait_note}")
    
    if is_game_day:
        lines.append("\n🏈 Game day crowds factored in!")
    
    return "\n".join(lines)


def check_model_health() -> Dict[str, Any]:
    """Check model health status."""
    status = {
        "backend": MODEL_BACKEND,
        "available": False,
        "message": "",
        "gpu_available": False
    }
    
    try:
        import torch
        status["gpu_available"] = torch.cuda.is_available()
        if status["gpu_available"]:
            status["gpu_name"] = torch.cuda.get_device_name(0)
    except:
        pass
    
    if MODEL_BACKEND == "local":
        if status["gpu_available"]:
            model, tokenizer = load_model_local()
            status["available"] = model is not None
            status["message"] = "Model loaded" if model else "Failed to load"
        else:
            status["available"] = False
            status["message"] = "No GPU available"
    
    elif MODEL_BACKEND == "huggingface":
        status["available"] = bool(HF_API_TOKEN)
        status["message"] = "HF configured" if status["available"] else "Missing HF config"
    
    else:
        status["available"] = False
        status["message"] = "Model disabled - using rule-based responses"
    
    return status
