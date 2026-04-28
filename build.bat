@echo off
echo ==============================================
echo CV-Auto PyInstaller 빌드 스크립트 시작
echo ==============================================

python -m PyInstaller --noconfirm --onedir --windowed ^
  --name "CV-Auto" ^
  --add-data "app.py;." ^
  --add-data "core;core" ^
  --add-data "prompts;prompts" ^
  --copy-metadata streamlit ^
  --copy-metadata google-genai ^
  --copy-metadata pydantic ^
  --hidden-import "core.cache_manager" ^
  --hidden-import "core.llm_engine" ^
  --hidden-import "core.logger" ^
  --hidden-import "core.pdf_parser" ^
  --hidden-import "core.search_utils" ^
  --hidden-import "prompts.templates" ^
  --hidden-import "pdfplumber" ^
  --hidden-import "google.genai" ^
  --hidden-import "pydantic" ^
  --hidden-import "streamlit" ^
  run_app.py

echo ==============================================
echo 빌드가 완료되었습니다! 
echo dist 폴더 안에 'CV-Auto' 폴더를 확인해 주세요.
echo ==============================================
