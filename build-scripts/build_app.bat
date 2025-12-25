@echo off
REM 실행 파일 빌드 스크립트 (Windows용)

echo =========================================
echo 토지거래허가구역 크롤러 빌드 시작
echo =========================================

REM Playwright 브라우저 확인
echo Playwright 브라우저 확인 중...
uv run playwright install chromium

REM PyInstaller로 실행 파일 생성
echo 실행 파일 생성 중...
uv run pyinstaller --clean ^
    --name "토지거래허가구역크롤러" ^
    --windowed ^
    --onefile ^
    --hidden-import playwright ^
    --hidden-import playwright.sync_api ^
    --hidden-import pandas ^
    --hidden-import requests ^
    토지거래허가구역_GUI.py

echo =========================================
echo 빌드 완료!
echo 실행 파일 위치: dist\토지거래허가구역크롤러.exe
echo =========================================
pause
