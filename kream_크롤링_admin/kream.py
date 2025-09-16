import time
from pathlib import Path
import sqlite3

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False

# DB: 경로/연결
DB_PATH = Path(__file__).with_name("products.db")
def get_conn():
    return sqlite3.connect(DB_PATH)

def create_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            brand TEXT,
            product_name TEXT,
            price INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_to_db(category, brand, product_name, price):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (category, brand, product_name, price) VALUES (?, ?, ?, ?)",
        (category, brand, product_name, price)
    )
    conn.commit()
    conn.close()

# Selenium 드라이버
def setup_driver(headless=False):
    header_user = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    options_ = Options()
    options_.add_argument(f"user-agent={header_user}")
    options_.add_argument("--disable-gpu")
    options_.add_argument("--no-sandbox")
    options_.add_argument("--window-size=1280,1600")
    if headless:
        options_.add_argument("--headless=new")
    # 불필요 로그 제거
    options_.add_experimental_option('excludeSwitches', ["enable-logging"])

    if USE_WDM:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options_)
    else:
        # 로컬에 chromedriver PATH가 잡혀 있으면 여기로도 동작
        driver = webdriver.Chrome(options=options_)
    driver.set_page_load_timeout(30)
    return driver

# 유틸: 스크롤해서 로딩 
def scroll_to_load(driver, min_scrolls=8, max_scrolls=40, pause=0.35):
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    stable = 0

    while scrolls < max_scrolls:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        scrolls += 1

        if new_height == last_height:
            stable += 1
        else:
            stable = 0
        last_height = new_height

        if scrolls >= min_scrolls and stable >= 2:
            break

# KREAM 검색
def search_product(driver, keyword):
    driver.get("https://kream.co.kr/")

    wait = WebDriverWait(driver, 15)

    # 쿠키/배너 닫기
    for sel in [
        "button[aria-label='닫기']",
        ".btn_close", ".btn-cancel", ".button-close", "button.close"
    ]:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            btn.click()
            break
        except:
            pass

    # 검색 버튼 클릭 
    button_selectors = [
        ".btn_search.header-search-button.search-button-margin",
        "button.btn_search",
        "button[aria-label='검색']",
        "a[href*='search']",
        ".search-btn",
    ]
    search_button = None
    for sel in button_selectors:
        try:
            search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            search_button.click()
            break
        except:
            continue
    if not search_button:
        raise RuntimeError("검색 버튼을 찾지 못했습니다. 셀렉터를 확인하세요.")

    # 검색 입력창 선택
    input_selectors = [
        ".input_search.show_placeholder_on_focus",
        "input.input_search",
        "input[type='search']",
        "input[placeholder*='검색']",
    ]
    search_input = None
    for sel in input_selectors:
        try:
            search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            break
        except:
            continue
    if not search_input:
        raise RuntimeError("검색 입력창을 찾지 못했습니다. 셀렉터를 확인하세요.")

    search_input.clear()
    search_input.send_keys(keyword)
    search_input.send_keys(Keys.ENTER)

    # 결과 영역 등장 대기
    result_container_selectors = [
        ".search_result", ".search_result_list", ".product_list", ".search_container", ".wrap", "main"
    ]
    found_container = False
    for sel in result_container_selectors:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            found_container = True
            break
        except:
            continue
    if not found_container:
        time.sleep(1.2)

    # 충분히 스크롤해서 아이템 로딩
    scroll_to_load(driver, min_scrolls=10, max_scrolls=50, pause=0.35)

# 파서: 결과에서 상품 추출
def extract_product_info_from_html(html, category):
    soup = BeautifulSoup(html, "html.parser")

    # 아이템 셀렉터 후보 (개편 대비 다중)
    item_selectors = [
        ".item_inner",
        ".search_result_item",
        ".product_card",
        "li[class*='product']",
        "div[class*='product']",
    ]
    items = []
    for sel in item_selectors:
        items = soup.select(sel)
        if items:
            break

    def pick_one(el, selectors):
        for sel in selectors:
            node = el.select_one(sel)
            if node:
                txt = node.get_text(strip=True)
                if txt:
                    return txt
        return ""

    def to_int_price(text):
        digits = "".join(ch for ch in str(text) if ch.isdigit())
        return int(digits) if digits else 0

    saved = 0
    for item in items:
        brand = pick_one(item, [".brand", ".product_info .brand", ".brand-text", "[class*='brand']"])
        product_name = pick_one(item, [".name", ".product_info .name", ".product_title", ".title", "[class*='name']"])
        price_text = pick_one(item, [".price", ".num.price", ".amount", ".product_info .price", "[class*='price']"])
        price = to_int_price(price_text)

        # 너무 빈 항목은 스킵
        if not (brand or product_name):
            continue

        print(f"[{category}] {brand} | {product_name} | {price}")
        save_to_db(category, brand, product_name, price)
        saved += 1
    return saved

# 메인
def main():
    create_table()
    categories = ["상의", "하의", "신발", "패션잡화"]

    driver = setup_driver(headless=False)
    total_saved = 0
    try:
        for category in categories:
            print(f"\n===== '{category}' 카테고리 검색 시작 =====")
            search_product(driver, category)

            # 스크롤 이후 잠깐 안정화
            time.sleep(0.8)

            html = driver.page_source
            saved = extract_product_info_from_html(html, category)
            print(f"→ '{category}' 저장 개수: {saved}")
            total_saved += saved

    finally:
        driver.quit()

    print(f"\n✅ 총 저장 개수: {total_saved}")

if __name__ == "__main__":
    main()
