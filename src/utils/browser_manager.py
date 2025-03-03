import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
import json
import os
import time
import ssl
import certifi
from webdriver_manager.chrome import ChromeDriverManager
import platform
import shutil
import urllib.request
import zipfile

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
        
        # 创建 Chrome 选项
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        
        # 设置下载路径
        os.makedirs(self.error_logs_dir, exist_ok=True)
        
        # 尝试在以下位置查找本地 ChromeDriver
        driver_paths = [
            './chromedriver',  # 项目根目录
            './drivers/chromedriver',  # drivers 子目录
            '/usr/local/bin/chromedriver',  # 系统路径
        ]
        
        for driver_path in driver_paths:
            try:
                if os.path.exists(driver_path):
                    logger.info(f"尝试使用本地 ChromeDriver: {driver_path}")
                    service = Service(driver_path)
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.set_page_load_timeout(300)
                    self.wait = WebDriverWait(self.driver, 10)
                    logger.info("浏览器: 使用本地 ChromeDriver 初始化成功")
                    return
            except Exception as e:
                logger.warning(f"使用本地 ChromeDriver {driver_path} 失败: {str(e)}")
        
        # 如果本地驱动都失败，则尝试自动下载
        try:
            logger.info("尝试自动下载 ChromeDriver...")
            
            # 清理可能损坏的缓存
            cache_dir = os.path.expanduser('~/.wdm')
            if os.path.exists(cache_dir):
                logger.info("清理旧的驱动缓存...")
                shutil.rmtree(cache_dir)
            
            # 创建下载目录
            drivers_dir = './drivers'
            os.makedirs(drivers_dir, exist_ok=True)
            
            # 获取 Chrome 版本
            chrome_version = None
            try:
                chrome_process = os.popen('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version')
                chrome_version = chrome_process.read().strip().split()[-1]  # 获取版本号
                chrome_process.close()
            except Exception as e:
                logger.error(f"获取 Chrome 版本失败: {str(e)}")
                raise
            
            logger.info(f"检测到 Chrome 版本: {chrome_version}")
            
            # 下载对应版本的 ChromeDriver
            # 构造下载 URL (使用 Chrome for Testing)
            os_type = platform.system().lower()
            is_arm = platform.machine().lower().startswith(('arm', 'aarch'))
            arch = 'arm64' if is_arm else 'x64'
            
            download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{chrome_version}/mac-{arch}/chromedriver-mac-{arch}.zip"
            zip_path = os.path.join(drivers_dir, 'chromedriver.zip')
            driver_path = os.path.join(drivers_dir, 'chromedriver')
            
            # 创建自定义的 SSL 上下文
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 下载文件
            logger.info(f"下载 ChromeDriver: {download_url}")
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(download_url, zip_path)
            
            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(drivers_dir)
            
            # 移动 chromedriver 到正确位置
            extracted_driver = os.path.join(drivers_dir, f'chromedriver-mac-{arch}', 'chromedriver')
            if os.path.exists(driver_path):
                os.remove(driver_path)
            shutil.move(extracted_driver, driver_path)
            
            # 设置执行权限
            os.chmod(driver_path, 0o755)
            
            # 清理临时文件
            os.remove(zip_path)
            shutil.rmtree(os.path.join(drivers_dir, f'chromedriver-mac-{arch}'))
            
            # 使用下载的驱动
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(300)
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("浏览器: 使用自动下载的 ChromeDriver 初始化成功")
            
        except Exception as e:
            logger.error(f"浏览器初始化失败: {str(e)}")
            raise
    
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
            if not cookies:
                logger.warning(f"没有可保存的 cookies: {domain}")
                return
            
            # 先读取现有内容
            existing_content = ''
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read().strip()
            
            # 将新的 cookies 转换为文本
            cookie_text = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
            
            # 如果现有内容非空且与新内容不同，创建备份
            if existing_content and existing_content != cookie_text:
                backup_file = f"{cookie_file}.bak"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(existing_content)
                logger.info(f"已创建cookie备份: {backup_file}")
            
            # 保存新的 cookies
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookie_text)
            logger.info(f"Cookie管理: 已保存 {domain} 的 cookies")
            
        except Exception as e:
            logger.error(f"Cookie错误: 保存 {domain} 的 cookies 失败 - {str(e)}")
    
    def load_cookies(self, domain: str) -> bool:
        """加载指定域名的 cookies"""
        cookie_file = os.path.join(self.cookies_dir, f"{domain}.txt")
        if not os.path.exists(cookie_file):
            logger.debug(f"Cookie文件不存在: {cookie_file}")
            return False
        
        try:
            # 先访问对应域名的网站
            if domain == 'baidu.com':
                self.driver.get('https://www.baidu.com')
            elif domain == 'bing.com':
                self.driver.get('https://cn.bing.com')
            time.sleep(2)  # 等待页面加载
            
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_text = f.read().strip()
                if not cookie_text:
                    logger.warning(f"Cookie文件为空: {cookie_file}")
                    return False
                
                cookie_list = [item.strip() for item in cookie_text.split(';') if item.strip()]
                for cookie_item in cookie_list:
                    try:
                        name, value = cookie_item.split('=', 1)
                        self.driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': domain  # 移除前导点号
                        })
                    except Exception as e:
                        logger.error(f"添加单个cookie失败: {cookie_item} - {str(e)}")
                        continue
                    
            logger.info(f"已加载 {domain} 的 cookies")
            return True
            
        except Exception as e:
            logger.error(f"加载 cookies 失败: {str(e)}")
            return False 