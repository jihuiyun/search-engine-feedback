import logging
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
import json
import os

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self):
        self.driver = None
        self.cookies_dir = "cookies"  # cookie 保存目录
        self.error_logs_dir = "error_logs"  # 添加错误日志目录
        for directory in [self.cookies_dir, self.error_logs_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.init_browser()
    
    def init_browser(self):
        """初始化浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 10)
        
    def check_browser(self):
        """检查浏览器是否正常"""
        try:
            # 尝试执行一个简单的操作来检查浏览器状态
            self.driver.current_url
            return True
        except WebDriverException:
            logger.warning("浏览器连接断开，尝试重新初始化...")
            self.init_browser()
            return False
    
    def quit(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def save_cookies(self, domain: str):
        """保存指定域名的 cookies"""
        cookies_path = os.path.join(self.cookies_dir, f"{domain}.json")
        cookies = self.driver.get_cookies()
        with open(cookies_path, 'w') as f:
            json.dump(cookies, f)
        logger.info(f"已保存 {domain} 的 cookies")
    
    def load_cookies(self, domain: str) -> bool:
        """加载指定域名的 cookies"""
        cookies_path = os.path.join(self.cookies_dir, f"{domain}.json")
        if not os.path.exists(cookies_path):
            return False
            
        try:
            with open(cookies_path, 'r') as f:
                cookies = json.load(f)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加 cookie 失败: {str(e)}")
            logger.info(f"已加载 {domain} 的 cookies")
            return True
        except Exception as e:
            logger.error(f"加载 cookies 失败: {str(e)}")
            return False 