"""
서울시 토지거래허가구역 크롤러 웹 애플리케이션
Flask 기반 웹 인터페이스
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime
from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import os
import json
import threading
import queue
import webbrowser
from threading import Timer

app = Flask(__name__)
CORS(app)

# 전역 변수
crawling_status = {
    "is_running": False,
    "progress": 0,
    "current_district": "",
    "total_rows": 0,
    "message": "대기 중...",
}
log_queue = queue.Queue()
stop_flag = threading.Event()


def convert_to_road_address(jibun_address, api_key):
    """지번 주소를 도로명 주소로 변환"""
    if not api_key:
        return ""

    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
    params = {
        "confmKey": api_key,
        "currentPage": 1,
        "countPerPage": 1,
        "keyword": jibun_address,
        "resultType": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("results", {}).get("common", {}).get("errorCode") == "0":
                juso_list = data.get("results", {}).get("juso", [])
                if juso_list:
                    return juso_list[0].get("roadAddr", "")
    except:
        pass
    return ""


def get_coordinates(address, kakao_api_key):
    """주소를 좌표로 변환"""
    if not address or not kakao_api_key:
        return "", ""

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {"query": address}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            documents = data.get("documents", [])
            if documents:
                return documents[0].get("y", ""), documents[0].get("x", "")
    except:
        pass
    return "", ""


def log_message(message):
    """로그 메시지 추가"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_queue.put(f"[{timestamp}] {message}")


def crawl_land_contracts(config):
    """크롤링 메인 함수"""
    global crawling_status, stop_flag

    try:
        stop_flag.clear()
        crawling_status["is_running"] = True
        crawling_status["progress"] = 0
        crawling_status["total_rows"] = 0
        log_message("크롤링을 시작합니다...")

        api_key = config["api_key"]
        kakao_api_key = config["kakao_api_key"]
        start_date = config["start_date"]
        end_date = config["end_date"]
        save_path = config["save_path"]
        headless = config["headless"]

        all_data = []

        with sync_playwright() as p:
            log_message("브라우저를 실행합니다...")
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()

            try:
                url = "https://land.seoul.go.kr/land/other/contractStatus.do"
                page.goto(url)
                page.wait_for_selector("#selectSigungu")

                log_message(f"수집 기간: {start_date} ~ {end_date}")

                # 구/군 옵션 가져오기
                district_options = page.locator("#selectSigungu option").all()
                district_values = [
                    opt.get_attribute("value")
                    for opt in district_options
                    if opt.get_attribute("value") != "11000"
                ]

                total_districts = len(district_values)
                log_message(f"총 {total_districts}개 구/군 데이터를 수집합니다.")

                # 각 구/군 순회
                for idx, district_code in enumerate(district_values, 1):
                    if stop_flag.is_set():
                        log_message("사용자가 중지를 요청했습니다.")
                        break

                    page.goto(url)
                    page.wait_for_selector("#selectSigungu")

                    # 구/군 선택
                    page.select_option("#selectSigungu", district_code)
                    district_name = page.locator(
                        "#selectSigungu option:checked"
                    ).inner_text()

                    crawling_status["current_district"] = district_name
                    crawling_status["progress"] = int((idx / total_districts) * 100)
                    log_message(f"[{idx}/{total_districts}] {district_name} 처리 중...")

                    # 날짜 입력
                    start_input = page.locator("#changeBgnde")
                    start_input.evaluate("el => el.removeAttribute('readonly')")
                    start_input.fill(start_date)

                    end_input = page.locator("#changeEndde")
                    end_input.evaluate("el => el.removeAttribute('readonly')")
                    end_input.fill(end_date)

                    # 검색
                    page.click("#search")
                    page.wait_for_timeout(2000)

                    # 페이지네이션
                    page_num = 1
                    while not stop_flag.is_set():
                        try:
                            page.wait_for_selector("#resultList_pc", timeout=5000)
                            rows = page.locator("#resultList_pc tr").all()
                        except:
                            break

                        if not rows:
                            break

                        if (
                            len(rows) == 1
                            and "조회된 내용이 없습니다" in rows[0].inner_text()
                        ):
                            break

                        # 데이터 추출
                        for row in rows:
                            cols = row.locator("td").all()
                            if len(cols) <= 1:
                                continue

                            row_data = [col.inner_text().strip() for col in cols]

                            # 주소 변환
                            jibun_addr = row_data[1]
                            road_addr = convert_to_road_address(jibun_addr, api_key)
                            row_data.append(road_addr)

                            # 좌표 변환
                            search_addr = jibun_addr if jibun_addr else road_addr
                            lat, lng = get_coordinates(search_addr, kakao_api_key)
                            if not lat and road_addr and jibun_addr:
                                lat, lng = get_coordinates(road_addr, kakao_api_key)

                            row_data.append(lat)
                            row_data.append(lng)
                            all_data.append(row_data)

                        crawling_status["total_rows"] = len(all_data)

                        # 다음 페이지
                        next_page_num = page_num + 1
                        next_btn = page.locator(
                            f"a[onclick*='fn_link_page({next_page_num})']"
                        )

                        if next_btn.count() > 0:
                            next_btn.first.click()
                            page_num += 1
                            page.wait_for_timeout(1500)
                        else:
                            break

                    log_message(f"{district_name} 완료 (현재까지 {len(all_data)}건)")

            finally:
                browser.close()

        # 데이터 저장
        if all_data and not stop_flag.is_set():
            columns = [
                "연번",
                "주소",
                "지번(지목)",
                "허가년월일",
                "이용목적",
                "이용의무종료일",
                "허가사항",
                "도로명주소",
                "위도",
                "경도",
            ]
            df = pd.DataFrame(all_data, columns=columns)

            today = datetime.today().strftime("%y%m%d")
            filename = f"토지거래허가구역_서울_{today}.csv"
            filepath = os.path.join(save_path, filename)

            df.to_csv(filepath, index=False, encoding="utf-8-sig")
            log_message(f"✓ 저장 완료: {filepath}")
            log_message(f"✓ 총 {len(df)}건의 데이터를 수집했습니다.")
            crawling_status["message"] = f"완료! 총 {len(df)}건 수집"
        elif stop_flag.is_set():
            log_message("크롤링이 중지되었습니다.")
            crawling_status["message"] = "중지됨"
        else:
            log_message("수집된 데이터가 없습니다.")
            crawling_status["message"] = "데이터 없음"

    except Exception as e:
        log_message(f"오류 발생: {str(e)}")
        crawling_status["message"] = f"오류: {str(e)}"

    finally:
        crawling_status["is_running"] = False
        crawling_status["progress"] = 100


@app.route("/")
def index():
    """메인 페이지"""
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start_crawling():
    """크롤링 시작"""
    if crawling_status["is_running"]:
        return jsonify({"error": "이미 크롤링이 진행 중입니다."}), 400

    config = request.json

    # 입력 검증
    if not config.get("api_key") or not config.get("kakao_api_key"):
        return jsonify({"error": "API 키를 입력해주세요."}), 400

    # 별도 스레드에서 크롤링 실행
    thread = threading.Thread(target=crawl_land_contracts, args=(config,), daemon=True)
    thread.start()

    return jsonify({"message": "크롤링을 시작했습니다."})


@app.route("/stop", methods=["POST"])
def stop_crawling():
    """크롤링 중지"""
    stop_flag.set()
    return jsonify({"message": "중지 요청을 보냈습니다."})


@app.route("/status")
def get_status():
    """상태 조회"""
    return jsonify(crawling_status)


@app.route("/logs")
def stream_logs():
    """로그 스트리밍 (Server-Sent Events)"""

    def generate():
        while True:
            try:
                message = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'message': message})}\n\n"
            except queue.Empty:
                # 연결 유지를 위한 heartbeat
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def open_browser():
    """브라우저 자동 열기"""
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    # 1초 후 브라우저 자동 열기
    Timer(1, open_browser).start()

    print("=" * 50)
    print("서울시 토지거래허가구역 크롤러 시작")
    print("브라우저에서 http://127.0.0.1:5000 을 열어주세요")
    print("=" * 50)

    app.run(debug=False, host="127.0.0.1", port=5000)
