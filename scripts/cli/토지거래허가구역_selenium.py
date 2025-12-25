from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
from datetime import datetime
import requests
import os


def convert_to_road_address(jibun_address, api_key):
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
    # 1. Setup Selenium WebDriver
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Uncomment if you want to run in headless mode
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # Get API Key for address conversion
    api_key = "U01TX0FVVEgyMDI1MTEyMjIzMjEwMDExNjQ4MzQ="
    kakao_api_key = "850d61a6084755000f7415664e58c1ee"

    try:
        # Navigate to the site
        url = "https://land.seoul.go.kr/land/other/contractStatus.do"
        driver.get(url)

        # Wait for the page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "selectSigungu")))

        # 2. 날짜 설정 - 사용자 입력
        print("=" * 60)
        print("토지거래허가구역 데이터 수집")
        print("=" * 60)
        print("※ 최대 조회 가능 기간: 60일")
        print("※ 날짜 형식: YYYY-MM-DD (예: 2025-11-01)")
        print("-" * 60)

        while True:
            start_date_str = input("시작일자를 입력하세요: ").strip()
            end_date_str = input("종료일자를 입력하세요: ").strip()

            try:
                # 날짜 유효성 검증
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

                # 날짜 순서 확인
                if start_date > end_date:
                    print("⚠️  오류: 시작일자가 종료일자보다 늦습니다. 다시 입력해주세요.\n")
                    continue

                # 60일 초과 여부 확인
                date_diff = (end_date - start_date).days
                if date_diff > 60:
                    print(f"⚠️  오류: 조회 기간이 {date_diff}일로 60일을 초과합니다. 다시 입력해주세요.\n")
                    continue

                # 정상 입력
                print(f"\n✓ 조회 기간: {start_date_str} ~ {end_date_str} ({date_diff + 1}일)")
                print("=" * 60)
                break

            except ValueError:
                print("⚠️  오류: 올바른 날짜 형식이 아닙니다. YYYY-MM-DD 형식으로 입력해주세요.\n")
                continue

        print(f"Crawling from {start_date_str} to {end_date_str}")
        # Get all district options
        select_element = driver.find_element(By.ID, "selectSigungu")
        select_object = Select(select_element)

        # Extract values for the 25 districts (skipping the first 'Select' option)
        district_options = [
            opt.get_attribute("value")
            for opt in select_object.options
            if opt.get_attribute("value") != "11000"
        ]

        all_data = []

        # 3. Loop through 25 districts
        for district_code in district_options:
            # Refresh page to avoid session timeout
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.ID, "selectSigungu")))

            # Re-find element to avoid StaleElementReferenceException
            select_element = driver.find_element(By.ID, "selectSigungu")
            select_object = Select(select_element)

            # Select district
            select_object.select_by_value(district_code)
            district_name = select_object.first_selected_option.text
            print(f"Processing: {district_name} ({district_code})")

            # Input Start Date - Use JS to set value directly to avoid input mask issues
            start_input = driver.find_element(By.ID, "changeBgnde")
            driver.execute_script(
                "arguments[0].removeAttribute('readonly');", start_input
            )  # readonly 속성 제거
            driver.execute_script(
                "arguments[0].value = arguments[1];", start_input, start_date_str
            )

            # Input End Date - Use JS to set value directly
            end_input = driver.find_element(By.ID, "changeEndde")
            driver.execute_script(
                "arguments[0].removeAttribute('readonly');", end_input
            )  # readonly 속성 제거
            driver.execute_script(
                "arguments[0].value = arguments[1];", end_input, end_date_str
            )

            # Click Search
            search_btn = driver.find_element(By.ID, "search")
            search_btn.click()

            # Wait for results to update
            time.sleep(2)

            # Pagination Loop
            page_num = 1
            while True:
                print(f"  Scraping page {page_num}...")
                # 4. Extract Data
                try:
                    tbody = driver.find_element(By.ID, "resultList_pc")
                    rows = tbody.find_elements(By.TAG_NAME, "tr")
                except:
                    print("  Result table not found.")
                    break

                if not rows or (
                    len(rows) == 1 and "조회된 내용이 없습니다" in rows[0].text
                ):
                    print(f"  No data for {district_name} on page {page_num}")
                    break

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) <= 1:
                        continue

                    # Extract text from each cell
                    row_data = [col.text.strip() for col in cols]

                    # Address Conversion
                    # row_data[1] is Address (e.g., 강남구 삼성동 105)
                    jibun_addr = row_data[1]
                    road_addr = ""

                    if api_key:
                        road_addr = convert_to_road_address(jibun_addr, api_key)

                    row_data.append(road_addr)

                    # Geocoding
                    lat, lng = "", ""
                    # Prefer Jibun Address for geocoding (more accurate for land), else Road Address
                    search_addr = jibun_addr if jibun_addr else road_addr

                    if kakao_api_key and search_addr:
                        lat, lng = get_coordinates(search_addr, kakao_api_key)
                        # If failed with jibun addr, try road addr
                        if not lat and road_addr and jibun_addr:
                            lat, lng = get_coordinates(road_addr, kakao_api_key)

                    row_data.append(lat)
                    row_data.append(lng)

                    all_data.append(row_data)

                # Check for Next Page
                # Look for a pagination link that corresponds to the next page number or a "Next" button
                # The site likely uses a function like fn_link_page(pageNo)
                try:
                    # Try to find the 'next' button (usually has an image or specific class)
                    # Or find the link for the next page number
                    next_page_num = page_num + 1

                    # XPath to find an 'a' tag that calls fn_link_page(next_page_num)
                    # This is a common pattern. If not, we look for the text of the number.
                    next_btn = driver.find_elements(
                        By.XPATH,
                        f"//a[contains(@onclick, 'fn_link_page({next_page_num})')]",
                    )

                    if next_btn:
                        next_btn[0].click()
                        page_num += 1
                        time.sleep(1.5)  # Wait for load
                    else:
                        # Try finding by text if onclick is not explicit
                        next_btn_text = driver.find_elements(
                            By.LINK_TEXT, str(next_page_num)
                        )
                        if next_btn_text:
                            next_btn_text[0].click()
                            page_num += 1
                            time.sleep(1.5)
                        else:
                            # No more pages found
                            break
                except Exception as e:
                    print(f"  Pagination ended or error: {e}")
                    break

    finally:
        driver.quit()
    # 5. Create DataFrame
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

    # Save to CSV
    today = datetime.today().strftime("%y%m%d")  # 251122 같은 형식
    save_dir = "/Volumes/T9/Tableau/찐투/0. Raw Data/토지거래허가구역"  # 저장 경로

    # Ensure directory exists
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
            print(f"Created directory: {save_dir}")
        except OSError as e:
            print(f"Error creating directory {save_dir}: {e}")
            print("Saving to current directory instead.")
            save_dir = "."
    filename = f"토지거래허가구역_서울_{today}.csv"  # 파일명
    filepath = os.path.join(save_dir, filename)  # 파일 경로
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved to {filepath}")
