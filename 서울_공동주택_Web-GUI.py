"""
서울시 공동주택 정보 수집기 웹 애플리케이션
Flask 기반 웹 인터페이스
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import pandas as pd
import requests
import time
import json
import threading
import queue
import webbrowser
from threading import Timer
import os

app = Flask(__name__)
CORS(app)

# 전역 변수
collection_status = {
    "is_running": False,
    "progress": 0,
    "current_batch": "",
    "total_records": 0,
    "message": "대기 중...",
}
log_queue = queue.Queue()
stop_flag = threading.Event()


def log_message(message):
    """로그 메시지 추가"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_queue.put(f"[{timestamp}] {message}")


def fetch_apartment_data(config):
    """공동주택 데이터 수집"""
    global collection_status, stop_flag

    try:
        stop_flag.clear()
        collection_status["is_running"] = True
        collection_status["progress"] = 0
        collection_status["total_records"] = 0

        api_key = config["api_key"]
        kakao_api_key = config["kakao_api_key"]
        save_path = config["save_path"]
        batch_size = config.get("batch_size", 1000)

        log_message("데이터 수집을 시작합니다...")

        # API 설정
        service_name = "OpenAptInfo"
        base_url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/{service_name}"

        all_data = []
        start_index = 1

        while not stop_flag.is_set():
            end_index = start_index + batch_size - 1
            collection_status["current_batch"] = f"{start_index}~{end_index}"
            log_message(f"레코드 {start_index} ~ {end_index} 수집 중...")

            # API 호출
            url = f"{base_url}/{start_index}/{end_index}/"
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                # API 에러 체크
                if service_name not in data:
                    if "RESULT" in data and "CODE" in data["RESULT"]:
                        log_message(f"API 메시지: {data['RESULT']['MESSAGE']}")
                    log_message("더 이상 데이터가 없습니다.")
                    break

                rows = data[service_name]["row"]
                all_data.extend(rows)
                collection_status["total_records"] = len(all_data)

                log_message(f"배치 완료: {len(rows)}개 수집 (누적: {len(all_data)}개)")

                # 데이터가 배치 크기보다 적으면 마지막
                if len(rows) < batch_size:
                    log_message("모든 데이터 수집 완료")
                    break

                start_index += batch_size
                collection_status["progress"] = min(
                    int((start_index / 3000) * 50), 50
                )  # 최대 50%

                time.sleep(0.1)  # API 호출 간격

            except requests.exceptions.RequestException as e:
                log_message(f"API 요청 실패: {e}")
                break
            except ValueError as e:
                log_message(f"JSON 파싱 실패: {e}")
                break

        if not all_data or stop_flag.is_set():
            if stop_flag.is_set():
                log_message("사용자가 중지했습니다.")
                collection_status["message"] = "중지됨"
            else:
                log_message("수집된 데이터가 없습니다.")
                collection_status["message"] = "데이터 없음"
            return

        log_message(f"총 {len(all_data)}개의 아파트 정보 수집 완료")
        collection_status["progress"] = 50

        # DataFrame 생성
        df = pd.DataFrame(all_data)

        # 컬럼명 한글화
        column_mapping = {
            "SN": "번호",
            "APT_CD": "아파트코드",
            "APT_NM": "아파트명",
            "CMPX_CLSF": "단지분류(아파트,주상복합등)",
            "APT_STDG_ADDR": "법정동주소",
            "APT_RDN_ADDR": "도로명주소",
            "CTPV_ADDR": "시도",
            "SGG_ADDR": "시군구",
            "EMD_ADDR": "읍면동",
            "DADDR": "상세주소",
            "RDN_ADDR": "도로명",
            "ROAD_DADDR": "도로명상세",
            "TELNO": "전화번호",
            "FXNO": "팩스번호",
            "APT_CMPX": "단지명",
            "APT_ATCH_FILE": "첨부파일",
            "HH_TYPE": "세대유형",
            "MNG_MTHD": "관리방식",
            "ROAD_TYPE": "도로유형",
            "MN_MTHD": "난방방식",
            "WHOL_DONG_CNT": "전체동수",
            "TNOHSH": "총세대수",
            "BLDR": "건설사",
            "DVLR": "시행사",
            "USE_APRV_YMD": "사용승인일",
            "GFA": "연면적",
            "RSDT_XUAR": "주거전용면적",
            "MNCO_LEVY_AREA": "관리비부과면적",
            "XUAR_HH_STTS60": "전용면적60㎡이하세대수",
            "XUAR_HH_STTS85": "전용면적60㎡초과85㎡이하세대수",
            "XUAR_HH_STTS135": "전용면적85㎡초과135㎡이하세대수",
            "XUAR_HH_STTS136": "전용면적135㎡초과세대수",
            "HMPG": "홈페이지",
            "REG_YMD": "등록일",
            "MDFCN_YMD": "수정일",
            "EPIS_MNG_NO": "단지관리번호",
            "EPS_MNG_FORM": "관리형태",
            "HH_ELCT_CTRT_MTHD": "세대전기계약방식",
            "CLNG_MNG_FORM": "청소관리형태",
            "BDAR": "건축면적",
            "PRK_CNTOM": "주차대수",
            "SE_CD": "구분코드",
            "CMPX_APRV_DAY": "단지승인일",
            "USE_YN": "사용여부",
            "MNCO_ULD_YN": "관리비업로드여부",
            "XCRD": "좌표X",
            "YCRD": "좌표Y",
            "CMPX_APLD_DAY": "단지신청일",
        }

        df.rename(columns=column_mapping, inplace=True)
        log_message("컬럼명 한글화 완료")

        # Kakao API로 지번 주소 변환
        if kakao_api_key and not stop_flag.is_set():
            log_message("Kakao API로 지번 주소 변환 시작...")
            collection_status["progress"] = 60

            def get_jibun_address(road_address):
                if not road_address or pd.isna(road_address):
                    return None

                url = "https://dapi.kakao.com/v2/local/search/address.json"
                headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
                params = {"query": road_address}

                try:
                    response = requests.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    result = response.json()

                    if result.get("documents"):
                        address_info = result["documents"][0].get("address")
                        if address_info:
                            return address_info.get("address_name")
                        return result["documents"][0].get("address_name")
                    return None
                except:
                    return None

            # 지번 주소 변환 (진행률 60% → 90%)
            total_count = len(df)
            for idx, row in df.iterrows():
                if stop_flag.is_set():
                    break
                df.at[idx, "지번주소"] = get_jibun_address(row.get("도로명주소"))
                if (idx + 1) % 100 == 0:
                    progress = 60 + int(((idx + 1) / total_count) * 30)
                    collection_status["progress"] = progress
                    log_message(f"지번 주소 변환 중... {idx + 1}/{total_count}")

            log_message("지번 주소 변환 완료")

        if stop_flag.is_set():
            log_message("사용자가 중지했습니다.")
            collection_status["message"] = "중지됨"
            return

        # 파일 저장
        collection_status["progress"] = 95
        from datetime import datetime

        today = datetime.today().strftime("%y%m%d")
        filename = f"서울_공동주택_{today}.csv"
        filepath = os.path.join(save_path, filename)

        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        log_message(f"✓ 저장 완료: {filepath}")
        log_message(f"✓ 총 {len(df)}개의 아파트 정보 저장")

        collection_status["progress"] = 100
        collection_status["message"] = f"완료! 총 {len(df)}개 수집"

    except Exception as e:
        log_message(f"오류 발생: {str(e)}")
        collection_status["message"] = f"오류: {str(e)}"

    finally:
        collection_status["is_running"] = False


@app.route("/")
def index():
    """메인 페이지"""
    return render_template("apartment_index.html")


@app.route("/start", methods=["POST"])
def start_collection():
    """데이터 수집 시작"""
    if collection_status["is_running"]:
        return jsonify({"error": "이미 수집이 진행 중입니다."}), 400

    config = request.json

    # 입력 검증
    if not config.get("api_key") or not config.get("kakao_api_key"):
        return jsonify({"error": "API 키를 입력해주세요."}), 400

    # 별도 스레드에서 수집 실행
    thread = threading.Thread(target=fetch_apartment_data, args=(config,), daemon=True)
    thread.start()

    return jsonify({"message": "데이터 수집을 시작했습니다."})


@app.route("/stop", methods=["POST"])
def stop_collection():
    """데이터 수집 중지"""
    stop_flag.set()
    return jsonify({"message": "중지 요청을 보냈습니다."})


@app.route("/status")
def get_status():
    """상태 조회"""
    return jsonify(collection_status)


@app.route("/logs")
def stream_logs():
    """로그 스트리밍"""

    def generate():
        while True:
            try:
                message = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'message': message})}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def open_browser():
    """브라우저 자동 열기"""
    webbrowser.open("http://127.0.0.1:5001")


if __name__ == "__main__":
    # 1초 후 브라우저 자동 열기
    Timer(1, open_browser).start()

    print("=" * 50)
    print("서울시 공동주택 정보 수집기 시작")
    print("브라우저에서 http://127.0.0.1:5001 을 열어주세요")
    print("=" * 50)

    app.run(debug=False, host="127.0.0.1", port=5001)
