# Implementation guide

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit DATABASE_URL with your MySQL username/password/database
python -m database.init_db
python -m datasets.dataset_loader gsm8k --limit 50
python main.py
streamlit run dashboard.py
pytest
```

Start llama.cpp separately and only on loopback, for example `llama-server -m models\qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 9931 -t 4 -c 2048`. Run one model server at a time on this 16 GiB integrated-GPU laptop. To collect two controlled configurations, change only threads/cache/output settings, perform warm-up plus repeated trials, and keep the same prepared prompts.
