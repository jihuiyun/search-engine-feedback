import logging
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
import json
import os
import time

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self):
        """初始化浏览器管理器"""
        # 禁用统计数据收集
        os.environ['WDM_DISABLE_USAGE_STATS'] = 'true'
        
        self.driver = None
        self.cookies_dir = "cookies"  # cookie 保存目录
        self.error_logs_dir = "error_logs"  # 添加错误日志目录
        for directory in [self.cookies_dir, self.error_logs_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.init_browser()
    
    def init_browser(self):
        """初始化浏览器"""
        logger.info("浏览器: 开始初始化...")
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if self.driver:
                    try:
                        self.driver.quit()
                        logger.debug("浏览器: 关闭旧实例")
                    except:
                        pass
                
                options = webdriver.ChromeOptions()
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--remote-debugging-port=0')  # 防止端口冲突
                
                self.driver = webdriver.Chrome(options=options)
                self.driver.maximize_window()
                self.wait = WebDriverWait(self.driver, 10)
                logger.info("浏览器: 初始化完成")
                return
                
            except Exception as e:
                retry_count += 1
                logger.error(f"浏览器初始化失败 (尝试 {retry_count}/{max_retries}): {str(e)}")
                time.sleep(2)
        
        raise Exception("浏览器初始化失败: 已达到最大重试次数")
    
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
        cookie_file = os.path.join(self.cookies_dir, f"{domain}.txt")
        try:
            cookies = self.driver.get_cookies()
            cookie_text = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
            
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookie_text)
            logger.info(f"Cookie管理: 已保存 {domain} 的 cookies")
        except Exception as e:
            logger.error(f"Cookie错误: 保存 {domain} 的 cookies 失败 - {str(e)}")
    
    def load_cookies(self, domain: str) -> bool:
        """加载指定域名的 cookies"""
        cookie_file = os.path.join(self.cookies_dir, f"{domain}.txt")
        if not os.path.exists(cookie_file):
            return False
        
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_text = f.read().strip()
                if cookie_text:
                    cookie_list = [item.strip() for item in cookie_text.split(';') if item.strip()]
                    for cookie_item in cookie_list:
                        name, value = cookie_item.split('=', 1)
                        self.driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': f".{domain}"
                        })
            logger.info(f"已加载 {domain} 的 cookies")
            return True
        except Exception as e:
            logger.error(f"加载 cookies 失败: {str(e)}")
            return False 