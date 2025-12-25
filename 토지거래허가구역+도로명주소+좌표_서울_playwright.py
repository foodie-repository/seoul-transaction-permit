from playwright.sync_api import sync_playwright
import pandas as pd
import time
from datetime import datetime
import requests
import os


def convert_to_road_address(jibun_address, api_key):
    """
    지번 주소를 도로명 주소로 변환하는 함수

    Args:
        jibun_address: 지번 주소
        api_key: 주소 API 키

    Returns:
        str: 도로명 주소 (변환 실패 시 빈 문자열)
    """
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
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("results", {}).get("common", {}).get("errorCode") == "0":
                juso_list = data.get("results", {}).get("juso", [])
                if juso_list:
                    return juso_list[0].get("roadAddr", "")
    except Exception as e:
        print(f"Error converting address {jibun_address}: {e}")

    return ""


def get_coordinates(address, kakao_api_key):
    """
    주소를 좌표(위도, 경도)로 변환하는 함수

    Args:
        address: 주소 (지번 또는 도로명)
        kakao_api_key: 카카오 API 키

    Returns:
        tuple: (위도, 경도) (변환 실패 시 ("", ""))
    """
    if not address or not kakao_api_key:
        return "", ""

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {"query": address}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            documents = data.get("documents", [])
            if documents:
                # Use the first result
                return documents[0].get("y", ""), documents[0].get("x", "")
    except Exception as e:
        print(f"Error geocoding address {address}: {e}")

    return "", ""


def crawl_land_contracts():
    """
    서울시 토지거래허가구역 정보를 크롤링하는 메인 함수

    Returns:
        DataFrame: 수집된 데이터
    """
    # API Keys
    api_key = "U01TX0FVVEgyMDI1MTEyMjIzMjEwMDExNjQ4MzQ="
    kakao_api_key = "850d61a6084755000f7415664e58c1ee"

    all_data = []

    with sync_playwright() as p:
        # 브라우저 실행 (headless=False로 설정하면 브라우저 창이 보임)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # 웹사이트 접속
            url = "https://land.seoul.go.kr/land/other/contractStatus.do"
            page.goto(url)

            # 페이지 로드 대기 (Playwright는 자동으로 대기하지만 명시적으로 확인)
            page.wait_for_selector("#selectSigungu")

            # 날짜 설정
            today = datetime.now()
            start_date_str = "2025-11-01"
            end_date_str = today.strftime("%Y-%m-%d")

            print(f"Crawling from {start_date_str} to {end_date_str}")

            # 구/군 옵션 가져오기
            district_options = page.locator("#selectSigungu option").all()
            district_values = [
                opt.get_attribute("value")
                for opt in district_options
                if opt.get_attribute("value") != "11000"
            ]

            # 25개 구/군 순회
            for district_code in district_values:
                # 세션 타임아웃 방지를 위해 페이지 새로고침
                page.goto(url)
                page.wait_for_selector("#selectSigungu")

                # 구/군 선택
                page.select_option("#selectSigungu", district_code)
                district_name = page.locator("#selectSigungu option:checked").inner_text()
                print(f"Processing: {district_name} ({district_code})")

                # 시작 날짜 입력
                start_input = page.locator("#changeBgnde")
                start_input.evaluate("el => el.removeAttribute('readonly')")
                start_input.fill(start_date_str)

                # 종료 날짜 입력
                end_input = page.locator("#changeEndde")
                end_input.evaluate("el => el.removeAttribute('readonly')")
                end_input.fill(end_date_str)

                # 검색 버튼 클릭
                page.click("#search")

                # 결과 로드 대기
                time.sleep(2)

                # 페이지네이션 처리
                page_num = 1
                while True:
                    print(f"  Scraping page {page_num}...")

                    # 결과 테이블 확인
                    try:
                        page.wait_for_selector("#resultList_pc", timeout=5000)
                        rows = page.locator("#resultList_pc tr").all()
                    except:
                        print("  Result table not found.")
                        break

                    # 데이터가 없는 경우 체크
                    if not rows:
                        print(f"  No data for {district_name} on page {page_num}")
                        break

                    # 첫 번째 행이 "조회된 내용이 없습니다"인 경우
                    if len(rows) == 1:
                        first_row_text = rows[0].inner_text()
                        if "조회된 내용이 없습니다" in first_row_text:
                            print(f"  No data for {district_name} on page {page_num}")
                            break

                    # 각 행 데이터 추출
                    for row in rows:
                        cols = row.locator("td").all()
                        if len(cols) <= 1:
                            continue

                        # 텍스트 추출
                        row_data = [col.inner_text().strip() for col in cols]

                        # 지번 주소 추출 (row_data[1])
                        jibun_addr = row_data[1]
                        road_addr = ""

                        # 도로명 주소 변환
                        if api_key:
                            road_addr = convert_to_road_address(jibun_addr, api_key)

                        row_data.append(road_addr)

                        # 좌표 변환
                        lat, lng = "", ""
                        # 지번 주소를 우선적으로 사용 (토지의 경우 더 정확함)
                        search_addr = jibun_addr if jibun_addr else road_addr

                        if kakao_api_key and search_addr:
                            lat, lng = get_coordinates(search_addr, kakao_api_key)
                            # 지번 주소로 실패하면 도로명 주소로 재시도
                            if not lat and road_addr and jibun_addr:
                                lat, lng = get_coordinates(road_addr, kakao_api_key)

                        row_data.append(lat)
                        row_data.append(lng)

                        all_data.append(row_data)

                    # 다음 페이지 확인
                    try:
                        next_page_num = page_num + 1

                        # fn_link_page(다음페이지번호)를 호출하는 링크 찾기
                        next_btn = page.locator(
                            f"a[onclick*='fn_link_page({next_page_num})']"
                        )

                        if next_btn.count() > 0:
                            next_btn.first.click()
                            page_num += 1
                            time.sleep(1.5)
                        else:
                            # onclick이 명시적이지 않은 경우 텍스트로 찾기
                            next_btn_text = page.locator(
                                f"a:has-text('{next_page_num}')"
                            )
                            if next_btn_text.count() > 0:
                                next_btn_text.first.click()
                                page_num += 1
                                time.sleep(1.5)
                            else:
                                # 더 이상 페이지가 없음
                                break
                    except Exception as e:
                        print(f"  Pagination ended or error: {e}")
                        break

        finally:
            browser.close()

    # DataFrame 생성
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

    return df


if __name__ == "__main__":
    df = crawl_land_contracts()
    print("Crawling Complete!")
    print(f"Total rows collected: {len(df)}")
    print(df.head())

    # CSV 저장
    today = datetime.today().strftime("%y%m%d")
    save_dir = "/Volumes/T9/Tableau/찐투/0. Raw Data/토지거래허가구역"

    # 디렉토리 확인 및 생성
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
            print(f"Created directory: {save_dir}")
        except OSError as e:
            print(f"Error creating directory {save_dir}: {e}")
            print("Saving to current directory instead.")
            save_dir = "."

    filename = f"토지거래허가구역_서울_{today}.csv"
    filepath = os.path.join(save_dir, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved to {filepath}")
