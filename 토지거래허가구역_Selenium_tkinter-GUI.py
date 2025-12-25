"""
서울시 토지거래허가구역 크롤러 GUI 버전
Playwright를 사용하여 데이터를 수집하고 CSV로 저장합니다.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
import threading
import os
import sys
from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import time


class LandCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("서울시 토지거래허가구역 크롤러")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # 변수 초기화
        self.is_running = False
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 제목
        title_label = ttk.Label(
            main_frame,
            text="서울시 토지거래허가구역 정보 수집기",
            font=("Arial", 16, "bold"),
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=10)

        # API 키 섹션
        api_frame = ttk.LabelFrame(main_frame, text="API 설정", padding="10")
        api_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # 주소 API 키
        ttk.Label(api_frame, text="주소 변환 API 키:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.api_key_var = tk.StringVar(
            value="U01TX0FVVEgyMDI1MTEyMjIzMjEwMDExNjQ4MzQ="
        )
        ttk.Entry(api_frame, textvariable=self.api_key_var, width=50).grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5
        )

        # 카카오 API 키
        ttk.Label(api_frame, text="카카오 API 키:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.kakao_key_var = tk.StringVar(value="850d61a6084755000f7415664e58c1ee")
        ttk.Entry(api_frame, textvariable=self.kakao_key_var, width=50).grid(
            row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5
        )

        # 날짜 섹션
        date_frame = ttk.LabelFrame(main_frame, text="수집 기간", padding="10")
        date_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # 시작 날짜
        ttk.Label(date_frame, text="시작 날짜 (YYYY-MM-DD):").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.start_date_var = tk.StringVar(value="2025-11-01")
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=20).grid(
            row=0, column=1, sticky=tk.W, pady=5, padx=5
        )

        # 종료 날짜
        ttk.Label(date_frame, text="종료 날짜 (YYYY-MM-DD):").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=20).grid(
            row=1, column=1, sticky=tk.W, pady=5, padx=5
        )

        # 저장 경로 섹션
        save_frame = ttk.LabelFrame(main_frame, text="저장 설정", padding="10")
        save_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(save_frame, text="저장 경로:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.save_path_var = tk.StringVar(value=os.path.expanduser("~/Desktop"))
        ttk.Entry(save_frame, textvariable=self.save_path_var, width=40).grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5
        )
        ttk.Button(save_frame, text="찾아보기", command=self.browse_folder).grid(
            row=0, column=2, pady=5, padx=5
        )

        # Headless 모드 체크박스
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            save_frame,
            text="Headless 모드 (브라우저 창 숨기기)",
            variable=self.headless_var,
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        # 실행 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        self.start_button = ttk.Button(
            button_frame,
            text="크롤링 시작",
            command=self.start_crawling,
            style="Accent.TButton",
        )
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(
            button_frame, text="중지", command=self.stop_crawling, state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=5)

        # 진행 상황 표시
        progress_frame = ttk.LabelFrame(main_frame, text="진행 상황", padding="10")
        progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.progress_var = tk.StringVar(value="대기 중...")
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(
            row=0, column=0, sticky=tk.W
        )

        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="indeterminate", length=600
        )
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        # 로그 출력 영역
        log_frame = ttk.LabelFrame(main_frame, text="로그", padding="10")
        log_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, width=80, state=tk.DISABLED
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def browse_folder(self):
        """폴더 선택 다이얼로그"""
        folder = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if folder:
            self.save_path_var.set(folder)

    def log(self, message):
        """로그 메시지 출력"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_crawling(self):
        """크롤링 시작"""
        if self.is_running:
            messagebox.showwarning("경고", "이미 크롤링이 진행 중입니다.")
            return

        # 입력 검증
        if not self.api_key_var.get() or not self.kakao_key_var.get():
            messagebox.showerror("오류", "API 키를 입력해주세요.")
            return

        try:
            datetime.strptime(self.start_date_var.get(), "%Y-%m-%d")
            datetime.strptime(self.end_date_var.get(), "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("오류", "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
            return

        if not os.path.exists(self.save_path_var.get()):
            messagebox.showerror("오류", "저장 경로가 존재하지 않습니다.")
            return

        # UI 상태 변경
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_bar.start()
        self.progress_var.set("크롤링 진행 중...")

        # 로그 초기화
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # 별도 스레드에서 크롤링 실행
        thread = threading.Thread(target=self.run_crawling, daemon=True)
        thread.start()

    def stop_crawling(self):
        """크롤링 중지"""
        self.is_running = False
        self.log("사용자가 중지를 요청했습니다.")

    def run_crawling(self):
        """실제 크롤링 로직"""
        try:
            self.log("크롤링을 시작합니다...")
            all_data = []

            api_key = self.api_key_var.get()
            kakao_api_key = self.kakao_key_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            headless = self.headless_var.get()

            with sync_playwright() as p:
                self.log("브라우저를 실행합니다...")
                browser = p.chromium.launch(headless=headless)
                page = browser.new_page()

                try:
                    url = "https://land.seoul.go.kr/land/other/contractStatus.do"
                    page.goto(url)
                    page.wait_for_selector("#selectSigungu")

                    self.log(f"수집 기간: {start_date} ~ {end_date}")

                    # 구/군 옵션 가져오기
                    district_options = page.locator("#selectSigungu option").all()
                    district_values = [
                        opt.get_attribute("value")
                        for opt in district_options
                        if opt.get_attribute("value") != "11000"
                    ]

                    total_districts = len(district_values)
                    self.log(f"총 {total_districts}개 구/군 데이터를 수집합니다.")

                    # 각 구/군 순회
                    for idx, district_code in enumerate(district_values, 1):
                        if not self.is_running:
                            self.log("크롤링이 중지되었습니다.")
                            break

                        page.goto(url)
                        page.wait_for_selector("#selectSigungu")

                        # 구/군 선택
                        page.select_option("#selectSigungu", district_code)
                        district_name = page.locator(
                            "#selectSigungu option:checked"
                        ).inner_text()

                        self.log(f"[{idx}/{total_districts}] {district_name} 처리 중...")

                        # 날짜 입력
                        start_input = page.locator("#changeBgnde")
                        start_input.evaluate("el => el.removeAttribute('readonly')")
                        start_input.fill(start_date)

                        end_input = page.locator("#changeEndde")
                        end_input.evaluate("el => el.removeAttribute('readonly')")
                        end_input.fill(end_date)

                        # 검색
                        page.click("#search")
                        time.sleep(2)

                        # 페이지네이션
                        page_num = 1
                        while self.is_running:
                            try:
                                page.wait_for_selector("#resultList_pc", timeout=5000)
                                rows = page.locator("#resultList_pc tr").all()
                            except:
                                break

                            if not rows:
                                break

                            if len(rows) == 1 and "조회된 내용이 없습니다" in rows[0].inner_text():
                                break

                            # 데이터 추출
                            for row in rows:
                                cols = row.locator("td").all()
                                if len(cols) <= 1:
                                    continue

                                row_data = [col.inner_text().strip() for col in cols]

                                # 주소 변환
                                jibun_addr = row_data[1]
                                road_addr = self.convert_to_road_address(
                                    jibun_addr, api_key
                                )
                                row_data.append(road_addr)

                                # 좌표 변환
                                search_addr = jibun_addr if jibun_addr else road_addr
                                lat, lng = self.get_coordinates(
                                    search_addr, kakao_api_key
                                )
                                if not lat and road_addr and jibun_addr:
                                    lat, lng = self.get_coordinates(
                                        road_addr, kakao_api_key
                                    )

                                row_data.append(lat)
                                row_data.append(lng)
                                all_data.append(row_data)

                            # 다음 페이지
                            next_page_num = page_num + 1
                            next_btn = page.locator(
                                f"a[onclick*='fn_link_page({next_page_num})']"
                            )

                            if next_btn.count() > 0:
                                next_btn.first.click()
                                page_num += 1
                                time.sleep(1.5)
                            else:
                                break

                        self.log(f"{district_name} 완료 (현재까지 {len(all_data)}건)")

                finally:
                    browser.close()

            # 데이터프레임 생성 및 저장
            if all_data:
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
                filepath = os.path.join(self.save_path_var.get(), filename)

                df.to_csv(filepath, index=False, encoding="utf-8-sig")
                self.log(f"✓ 저장 완료: {filepath}")
                self.log(f"✓ 총 {len(df)}건의 데이터를 수집했습니다.")

                messagebox.showinfo("완료", f"크롤링이 완료되었습니다.\n총 {len(df)}건 수집")
            else:
                self.log("수집된 데이터가 없습니다.")
                messagebox.showwarning("경고", "수집된 데이터가 없습니다.")

        except Exception as e:
            self.log(f"오류 발생: {str(e)}")
            messagebox.showerror("오류", f"크롤링 중 오류가 발생했습니다.\n{str(e)}")

        finally:
            # UI 상태 복원
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_bar.stop()
            self.progress_var.set("완료")

    def convert_to_road_address(self, jibun_address, api_key):
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
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("results", {}).get("common", {}).get("errorCode") == "0":
                    juso_list = data.get("results", {}).get("juso", [])
                    if juso_list:
                        return juso_list[0].get("roadAddr", "")
        except:
            pass

        return ""

    def get_coordinates(self, address, kakao_api_key):
        """주소를 좌표로 변환"""
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
                    return documents[0].get("y", ""), documents[0].get("x", "")
        except:
            pass

        return "", ""


def main():
    root = tk.Tk()
    app = LandCrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
