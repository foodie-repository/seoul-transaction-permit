@echo off
REM 서울 공동주택 수집기 빌드 스크립트 (Windows용)

echo =========================================
echo 서울 공동주택 정보 수집기 빌드 시작
echo =========================================

REM 의존성 확인
echo 의존성 확인 중...
uv sync

REM PyInstaller로 실행 파일 생성
echo 실행 파일 생성 중...
uv run pyinstaller --clean ^
    --name "서울공동주택수집기" ^
    --windowed ^
    --onefile ^
    --add-data "templates;templates" ^
    --hidden-import flask ^
    --hidden-import flask_cors ^
    --hidden-import pandas ^
    --hidden-import requests ^
    서울_공동주택_Web-GUI.py

echo =========================================
echo 빌드 완료!
echo 실행 파일 위치: dist\서울공동주택수집기.exe
echo.
echo 사용 방법:
echo 1. 실행 파일을 더블클릭
echo 2. 자동으로 브라우저가 열립니다
echo 3. http://127.0.0.1:5001 에서 프로그램 사용
echo =========================================
pause
