# Local LLM Runtime Optimizer

An evidence-first local LLM optimization system for selecting a tested configuration under quality, latency, memory, and optional energy constraints. It extends the original llama.cpp CSV benchmark prototype without rewriting or overwriting historical data.

## Quick start

```powershell
cd "C:\Users\dipesh\Desktop\llm local runtime optimizer - Copy (2)\local-llm-runtime-optimizer"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
llama-server -m .\models\qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 9931 -t 4 -c 2048
```

In separate terminals:

```powershell
uvicorn api.app:app --host 127.0.0.1 --port 8001
streamlit run dashboard.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8001/docs` for the API. See `docs/` for MySQL setup, data preparation, limitations, experiment protocol, Responsible AI governance, and method details.

## Presentation demonstration

Start the local server, call `POST /api/v1/optimize` with a latency limit, then call `POST /api/v1/generate` with a short factual or reasoning prompt. Show the response metadata, the historical experiment table, and the dashboard’s explicit energy-unavailable state. This demonstrates the end-to-end flow without overstating unmeasured results.
