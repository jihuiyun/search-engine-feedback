import os
import sys
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def setup_chromedriver():
    """设置并安装 ChromeDriver"""
    try:
        # 检查 drivers 目录是否存在
        drivers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'drivers')
        if not os.path.exists(drivers_dir):
            os.makedirs(drivers_dir)
        
        chromedriver_path = os.path.join(drivers_dir, 'chromedriver')
        
        # 如果 chromedriver 不存在，则安装
        if not os.path.exists(chromedriver_path):
            print("ChromeDriver 不存在，正在安装...")
            # 使用 webdriver_manager 自动下载适合的 ChromeDriver
            driver_path = ChromeDriverManager().install()
            
            # 将下载的 ChromeDriver 复制到我们的 drivers 目录
            import shutil
            shutil.copy2(driver_path, chromedriver_path)
            
            # 在 Unix 系统上设置执行权限
            if platform.system() != 'Windows':
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