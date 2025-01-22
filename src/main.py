import logging
from src.utils.browser_manager import BrowserManager
from src.utils.processor import SearchProcessor
from src.engines.toutiao import ToutiaoEngine
# from engines.baidu import BaiduEngine  # 待实现
# from engines.bing import BingEngine    # 待实现
# from engines.qihoo import QihooEngine  # 待实现

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    browser_manager = BrowserManager()
    config_path = "config/config.yaml"
    
    try:
        # 初始化搜索引擎
        engines = {
            'toutiao': ToutiaoEngine(config_path, browser_manager)
        }
        
        # 创建处理器并运行
        processor = SearchProcessor(config_path, browser_manager.driver, engines)
        processor.run()
    finally:
        browser_manager.quit()

if __name__ == "__main__":
    main() 