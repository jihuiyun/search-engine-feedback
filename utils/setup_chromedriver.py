import os
import sys
import platform
import ssl
import certifi
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

def setup_chromedriver():
    """设置并安装 ChromeDriver"""
    try:
        # 设置 SSL 证书
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # 检查 drivers 目录是否存在
        drivers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'drivers')
        if not os.path.exists(drivers_dir):
            os.makedirs(drivers_dir)
        
        chromedriver_path = os.path.join(drivers_dir, 'chromedriver')
        
        # 如果 chromedriver 不存在，则安装
        if not os.path.exists(chromedriver_path):
            print("ChromeDriver 不存在，正在安装...")
            
            # 根据系统和架构设置下载选项
            os_type = platform.system().lower()
            is_arm = platform.machine().lower().startswith(('arm', 'aarch'))
            
            # 设置环境变量
            os.environ['WDM_SSL_VERIFY'] = '0'  # 禁用 SSL 验证
            if os_type == 'darwin':  # macOS
                if is_arm:
                    os.environ['WDM_ARCHITECTURE'] = 'arm64'
                else:
                    os.environ['WDM_ARCHITECTURE'] = 'x64'
            
            # 使用 webdriver_manager 自动下载适合的 ChromeDriver
            driver_path = ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install()
            
            # 将下载的 ChromeDriver 复制到我们的 drivers 目录
            import shutil
            shutil.copy2(driver_path, chromedriver_path)
            
            # 在 Unix 系统上设置执行权限
            if os_type != 'windows':
                os.chmod(chromedriver_path, 0o755)
            
            print(f"ChromeDriver 已安装到: {chromedriver_path}")
        else:
            print("ChromeDriver 已存在")
        
        return chromedriver_path
    
    except Exception as e:
        print(f"安装 ChromeDriver 时出错: {str(e)}")
        raise

if __name__ == "__main__":
    setup_chromedriver() 