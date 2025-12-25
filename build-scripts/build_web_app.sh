#!/bin/bash
# 웹 기반 실행 파일 빌드 스크립트 (Mac/Linux용)

echo "========================================="
echo "토지거래허가구역 크롤러 (웹버전) 빌드 시작"
echo "========================================="

# Playwright 브라우저 확인
echo "Playwright 브라우저 확인 중..."
uv run playwright install chromium

# PyInstaller로 실행 파일 생성
echo "실행 파일 생성 중..."
uv run pyinstaller --clean \
    --name "토지거래허가구역크롤러" \
    --windowed \
    --onefile \
    --add-data "scripts/gui/web/templates:templates" \
    --add-data "static:static" \
    --hidden-import flask \
    --hidden-import flask_cors \
    --hidden-import playwright \
    --hidden-import playwright.sync_api \
    --hidden-import pandas \
    --hidden-import requests \
    scripts/gui/web/토지거래허가구역_웹GUI.py

echo "========================================="
echo "빌드 완료!"
echo "실행 파일 위치: dist/토지거래허가구역크롤러"
echo ""
echo "사용 방법:"
echo "1. 실행 파일을 더블클릭"
echo "2. 자동으로 브라우저가 열립니다"
echo "3. http://127.0.0.1:5000 에서 프로그램 사용"
echo "========================================="
