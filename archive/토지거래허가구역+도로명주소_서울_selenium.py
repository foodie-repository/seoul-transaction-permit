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
        "resultType": "json"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('results', {}).get('common', {}).get('errorCode') == '0':
                juso_list = data.get('results', {}).get('juso', [])
                if juso_list:
                    return juso_list[0].get('roadAddr', "")
    except Exception as e:
        print(f"Error converting address {jibun_address}: {e}")
    
    return ""
def crawl_land_contracts():
    # 1. Setup Selenium WebDriver
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Uncomment if you want to run in headless mode
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Get API Key for address conversion
    api_key = "U01TX0FVVEgyMDI1MTEyMjIzMjEwMDExNjQ4MzQ="
    
    try:
        # Navigate to the site
        url = "https://land.seoul.go.kr/land/other/contractStatus.do"
        driver.get(url)
        
        # Wait for the page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "selectSigungu")))
        
        # 2. Date Calculation
        today = datetime.now()
        # First day of the current month
        start_date_str = today.strftime("%Y%m01")
        # Today's date
        end_date_str = today.strftime("%Y%m%d")
        
        print(f"Crawling from {start_date_str} to {end_date_str}")
        # Get all district options
        select_element = driver.find_element(By.ID, "selectSigungu")
        select_object = Select(select_element)
        
        # Extract values for the 25 districts (skipping the first 'Select' option)
        district_options = [opt.get_attribute("value") for opt in select_object.options if opt.get_attribute("value") != "11000"]
        
        all_data = []
        
        # 3. Loop through 25 districts
        for district_code in district_options:
            # Re-find element to avoid StaleElementReferenceException
            select_element = driver.find_element(By.ID, "selectSigungu")
            select_object = Select(select_element)
            
            # Select district
            select_object.select_by_value(district_code)
            district_name = select_object.first_selected_option.text
            print(f"Processing: {district_name} ({district_code})")
            
            # Input Start Date
            start_input = driver.find_element(By.ID, "changeBgnde")
            start_input.clear()
            start_input.send_keys(start_date_str)
            
            # Input End Date
            end_input = driver.find_element(By.ID, "changeEndde")
            end_input.clear()
            end_input.send_keys(end_date_str)
            
            # Click Search
            search_btn = driver.find_element(By.ID, "search")
            search_btn.click()
            
            # Wait for results to update
            time.sleep(1.5) 
            
            # 4. Extract Data
            tbody = driver.find_element(By.ID, "resultList_pc")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            if not rows:
                print(f"No data for {district_name}")
                continue
                
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) <= 1:
                    continue
                    
                # Extract text from each cell
                row_data = [col.text.strip() for col in cols]
                
                # Address Conversion
                # row_data[1] is Address (e.g., 강남구 삼성동 105)
                # row_data[2] is Ji-mok (e.g., 대) - Not part of address for search usually, but address column is full
                jibun_addr = row_data[1]
                road_addr = ""
                
                if api_key:
                    # Sometimes address needs cleaning or combining with district? 
                    # The table address usually includes district (e.g. "강남구 삼성동 105")
                    road_addr = convert_to_road_address(jibun_addr, api_key)
                
                row_data.append(road_addr)
                all_data.append(row_data)
                
    finally:
        driver.quit()
    # 5. Create DataFrame
    columns = ["연번", "주소", "지번(지목)", "허가년월일", "이용목적", "이용의무종료일", "허가사항", "도로명주소"]
    df = pd.DataFrame(all_data, columns=columns)
    
    return df
if __name__ == "__main__":
    df = crawl_land_contracts()
    print("Crawling Complete!")
    print(f"Total rows collected: {len(df)}")
    print(df.head())
    
    # Save to CSV
    today = datetime.today().strftime("%y%m%d") # 251122 같은 형식
    save_dir = "/Volumes/T9/Tableau/찐투/0. Raw Data/토지거래허가구역" # 저장 경로
    
    # Ensure directory exists
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
            print(f"Created directory: {save_dir}")
        except OSError as e:
            print(f"Error creating directory {save_dir}: {e}")
            print("Saving to current directory instead.")
            save_dir = "."
    filename = f"토지거래허가구역_서울_{today}.csv" # 파일명
    filepath = os.path.join(save_dir, filename) # 파일 경로
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved to {filepath}")