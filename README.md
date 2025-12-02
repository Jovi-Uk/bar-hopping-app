# 🍺 Lubbock Bar Hopping Route Optimizer

An AI-powered bar hopping assistant that optimizes your night out in Lubbock, Texas. Uses a fine-tuned Microsoft Phi-3.5 language model to understand natural language requests and generate conversational responses.

## What This Project Does

You tell it something like *"yo let's hit Chimy's and Cricket's at 9pm"* and it:
1. **Understands** your casual language (handles typos, nicknames, etc.)
2. **Optimizes** the order of bars to minimize your total wait time
3. **Responds** with a friendly, AI-generated itinerary

## Architecture

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│   React Frontend    │  HTTP   │       FastAPI Backend           │
│   (Vercel - free)   │ ◄─────► │     (Railway Pro - $5/mo)       │
│                     │         │                                 │
│  - Chat Interface   │         │  - NLU Service (parsing)        │
│  - Route Display    │         │  - Simulation (optimization)    │
│  - Model Status     │         │  - LLM Service (Phi-3.5)        │
└─────────────────────┘         └─────────────────────────────────┘
```

## Project Structure

```
bar-hopping-app/
├── backend/                    # FastAPI Python server
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # Entry point, CORS config
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   └── optimizer.py   # API endpoints
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── nlu.py         # Natural language understanding
│   │       ├── simulation.py  # Route optimization
│   │       └── model.py       # LLM integration
│   ├── requirements.txt
│   ├── .env.example
│   ├── railway.toml
│   └── Dockerfile
│
├── frontend/                   # React web application
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx/.css
│   │   │   ├── RouteDisplay.jsx/.css
│   │   │   └── BarList.jsx/.css
│   │   └── services/
│   │       └── api.js
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
│
├── .gitignore
└── README.md
```

## Quick Start (Local Development)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set MODEL_BACKEND=disabled for testing without GPU
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Visit http://localhost:5173

## Deployment

See the **Complete_Deployment_Guide.pdf** for step-by-step instructions.

**Quick summary:**
1. Push code to GitHub
2. Deploy backend to Railway Pro (has GPU support)
3. Deploy frontend to Vercel (free)
4. Configure environment variables

## Environment Variables

### Backend (Railway)
| Variable | Description |
|----------|-------------|
| MODEL_BACKEND | `local` (GPU), `huggingface`, or `disabled` |
| HF_MODEL_ID | `microsoft/Phi-3.5-mini-instruct` |
| HF_LORA_ID | Your fine-tuned adapter from HuggingFace Hub |
| ALLOWED_ORIGINS | Your Vercel frontend URL |

### Frontend (Vercel)
| Variable | Description |
|----------|-------------|
| VITE_API_URL | Your Railway backend URL + `/api` |

## Tech Stack

- **Frontend:** React 18, Vite, Axios, Lucide React
- **Backend:** FastAPI, Pydantic, uvicorn
- **ML:** PyTorch, Transformers, PEFT, bitsandbytes
- **Model:** Microsoft Phi-3.5-mini-instruct with LoRA fine-tuning

## Authors

Hannah Juscelino-Diogo & Jovi Ukwade
