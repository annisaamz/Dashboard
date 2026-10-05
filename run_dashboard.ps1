# Setup sekali jalan + start dashboard light mode (jalankan dari root etl-streaming-2)
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run dashboard_traffic_surabaya.py --theme.base light
