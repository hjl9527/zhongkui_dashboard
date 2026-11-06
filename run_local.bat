@echo off
cd /d "%~dp0"
set PYTHONPATH=C:\Users\hjl9527\Documents\Trae-CN\temp_20261029_01\_libs
set STREAMLIT_GLOBAL_DEVELOPMENT_MODE=false
echo Starting dashboard at http://localhost:8501 ...
python -m streamlit run app.py --server.port 8501
pause
