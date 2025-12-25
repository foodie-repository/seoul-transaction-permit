import requests
import pandas as pd
import time
import os

# API Configuration
API_KEY = '434a4e7a4665706f313035576e725a63'
SERVICE_NAME = 'OpenAptInfo'
BASE_URL = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/{SERVICE_NAME}'
BATCH_SIZE = 1000

def fetch_data(start_index, end_index):
    """Fetches data from the API for a given range."""
    url = f'{BASE_URL}/{start_index}/{end_index}/'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Check for API errors or empty results
        if SERVICE_NAME not in data:
            if 'RESULT' in data and 'CODE' in data['RESULT']:
                 print(f"API Message: {data['RESULT']['MESSAGE']}")
            return None
            
        return data[SERVICE_NAME]['row']
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except ValueError as e:
        print(f"JSON decode failed: {e}")
        return None

def main():
    all_data = []
    start_index = 1
    
    print("Starting data collection...")
    
    while True:
        end_index = start_index + BATCH_SIZE - 1
        print(f"Fetching records {start_index} to {end_index}...")
        
        rows = fetch_data(start_index, end_index)
        
        if not rows:
            print("No more data found or error occurred.")
            break
            
        all_data.extend(rows)
        
        # If we received fewer rows than requested, we've likely reached the end
        if len(rows) < BATCH_SIZE:
            print("Reached end of data.")
            break
            
        start_index += BATCH_SIZE
        time.sleep(0.1) # Be polite to the API

    if all_data:
        print(f"Total records collected: {len(all_data)}")
        df = pd.DataFrame(all_data)
        
        # Column renaming mapping
        column_mapping = {
            'SN': '번호',
            'APT_CD': '아파트코드',
            'APT_NM': '아파트명',
            'CMPX_CLSF': '단지분류(아파트,주상복합등)',
            'APT_STDG_ADDR': '법정동주소',
            'APT_RDN_ADDR': '도로명주소',
            'CTPV_ADDR': '시도',
            'SGG_ADDR': '시군구',
            'EMD_ADDR': '읍면동',
            'DADDR': '상세주소',
            'RDN_ADDR': '도로명',
            'ROAD_DADDR': '도로명상세',
            'TELNO': '전화번호',
            'FXNO': '팩스번호',
            'APT_CMPX': '단지명',
            'APT_ATCH_FILE': '첨부파일',
            'HH_TYPE': '세대유형',
            'MNG_MTHD': '관리방식',
            'ROAD_TYPE': '도로유형',
            'MN_MTHD': '난방방식',
            'WHOL_DONG_CNT': '전체동수',
            'TNOHSH': '총세대수',
            'BLDR': '건설사',
            'DVLR': '시행사',
            'USE_APRV_YMD': '사용승인일',
            'GFA': '연면적',
            'RSDT_XUAR': '주거전용면적',
            'MNCO_LEVY_AREA': '관리비부과면적',
            'XUAR_HH_STTS60': '전용면적60㎡이하세대수',
            'XUAR_HH_STTS85': '전용면적60㎡초과85㎡이하세대수',
            'XUAR_HH_STTS135': '전용면적85㎡초과135㎡이하세대수',
            'XUAR_HH_STTS136': '전용면적135㎡초과세대수',
            'HMPG': '홈페이지',
            'REG_YMD': '등록일',
            'MDFCN_YMD': '수정일',
            'EPIS_MNG_NO': '단지관리번호',
            'EPS_MNG_FORM': '관리형태',
            'HH_ELCT_CTRT_MTHD': '세대전기계약방식',
            'CLNG_MNG_FORM': '청소관리형태',
            'BDAR': '건축면적',
            'PRK_CNTOM': '주차대수',
            'SE_CD': '구분코드',
            'CMPX_APRV_DAY': '단지승인일',
            'USE_YN': '사용여부',
            'MNCO_ULD_YN': '관리비업로드여부',
            'XCRD': '좌표X',
            'YCRD': '좌표Y',
            'CMPX_APLD_DAY': '단지신청일'
        }
        
        df.rename(columns=column_mapping, inplace=True)

        # Kakao API for Jibun Address
        KAKAO_API_KEY = "850d61a6084755000f7415664e58c1ee"
        
        def get_jibun_address(road_address):
            if not road_address or pd.isna(road_address):
                return None
            
            url = "https://dapi.kakao.com/v2/local/search/address.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
            params = {"query": road_address}
            
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                result = response.json()
                
                if result.get('documents'):
                    # The first document usually contains the best match
                    address_info = result['documents'][0].get('address')
                    if address_info:
                        return address_info.get('address_name')
                    # Fallback if 'address' object is missing but 'address_name' exists in document (rare for address search)
                    return result['documents'][0].get('address_name')
                return None
            except Exception as e:
                print(f"Error fetching address for {road_address}: {e}")
                return None

        print("Fetching Jibun addresses from Kakao API...")
        # Using apply with a lambda to handle potential errors gracefully and show progress if needed
        # For better performance/progress indication, we could use tqdm, but simple apply is fine for ~3000 records
        df['지번주소'] = df['도로명주소'].apply(get_jibun_address)
        
        output_file = 'seoul_apartment_info.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"Data saved to {output_file}")
    else:
        print("No data collected.")

if __name__ == "__main__":
    main()
