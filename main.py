import logging
import os
from src.utils.browser_manager import BrowserManager
from src.utils.processor import SearchProcessor
from src.engines.toutiao import ToutiaoEngine
from src.engines.bing import BingEngine
from src.engines.baidu import BaiduEngine
import urllib3
from selenium.webdriver.remote.remote_connection import LOGGER as selenium_logger

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 禁用特定模块的日志
urllib3.disable_warnings()
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
selenium_logger.setLevel(logging.ERROR)  # 设置 Selenium 日志级别
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

def main():
    logger.info("程序启动: 初始化系统配置...")
    # 禁用 webdriver-manager 的统计数据收集
    os.environ['WDM_DISABLE_USAGE_STATS'] = 'true'
    
    browser_manager = BrowserManager()
    config_path = "config.yaml"
    
    try:
        # 初始化搜索引擎
        logger.info("初始化搜索引擎...")
        engines = {
            # 'baidu': BaiduEngine(config_path, browser_manager),
            'bing': BingEngine(config_path, browser_manager),
            # 'toutiao': ToutiaoEngine(config_path, browser_manager),
        }
        
        # 创建处理器并运行
        logger.info("开始执行搜索任务...")
        processor = SearchProcessor(config_path, browser_manager, engines)
        processor.run()
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
    finally:
        logger.info("程序结束: 正在清理资源...")
        browser_manager.quit()

if __name__ == "__main__":
    main() 