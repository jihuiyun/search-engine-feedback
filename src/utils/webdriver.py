from selenium import webdriver
from selenium.webdriver.chrome.service import Service

def init_driver():
    """初始化浏览器驱动"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 无头模式，如果需要的话
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # 指定本地 chromedriver 路径
    driver = webdriver.Chrome(
        service=Service("/Users/jihuiyun/chromedriver"),
        options=options
    )
    driver.maximize_window()
    return driver 