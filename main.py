import logging
import os
from src.utils.browser_manager import BrowserManager
from src.utils.processor import SearchProcessor
from src.engines.toutiao import ToutiaoEngine
from src.engines.bing import BingEngine
from src.engines.baidu import BaiduEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    # 禁用 webdriver-manager 的统计数据收集
    os.environ['WDM_DISABLE_USAGE_STATS'] = 'true'
    
    browser_manager = BrowserManager()
    config_path = "config.yaml"
    
    try:
        # 初始化搜索引擎
        engines = {
            # 'baidu': BaiduEngine(config_path, browser_manager),
            'bing': BingEngine(config_path, browser_manager),
            # 'toutiao': ToutiaoEngine(config_path, browser_manager),
        }
        
        # 创建处理器并运行
        processor = SearchProcessor(config_path, browser_manager, engines)
        processor.run()
    finally:
        browser_manager.quit()

if __name__ == "__main__":
    main() 