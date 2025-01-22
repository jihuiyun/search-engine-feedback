import yaml
import logging
import time
from typing import Dict
from selenium.webdriver.remote.webdriver import WebDriver
from src.database import Database
from src.engines.base import SearchEngine

logger = logging.getLogger(__name__)

class SearchProcessor:
    def __init__(self, config_path: str, browser_manager, engines: Dict[str, SearchEngine]):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.browser_manager = browser_manager
        self.driver = browser_manager.driver
        self.engines = engines
        # 初始化数据库
        self.db = Database(self.config['database']['path'])

    def process_keyword(self, engine_name: str, keyword: str):
        """处理单个关键词"""
        engine = self.engines[engine_name]
        current_page = self.db.get_progress(keyword, engine_name)
        logger.info(f"开始处理关键词: {keyword}, 引擎: {engine_name}, 从第 {current_page} 页继续")
        
        try:
            engine.search(keyword)
            
            for _ in range(1, current_page):
                if not engine.next_page():
                    return
            
            while True:
                results = engine.get_search_results()
                logger.info(f"当前页获取到 {len(results)} 条搜索结果")
                
                for index, result in enumerate(results, 1):
                    try:
                        logger.info(f"检查第 {index} 条结果: {result['title']}")
                        logger.info(f"URL: {result['url']}")
                        
                        is_expired = engine.check_expired(result['url'])
                        logger.info(f"检查结果: {'已过期' if is_expired else '正常'}")
                        
                        self.db.save_result({
                            'keyword': keyword,
                            'title': result['title'],
                            'url': result['url'],
                            'search_engine': engine_name,
                            'is_expired': is_expired
                        })
                        
                        if is_expired:
                            logger.info(f"发现过期链接，准备提交反馈: {result['url']}")
                            engine.submit_feedback(result)
                            time.sleep(1)
                            
                    except Exception as e:
                        logger.error(f"处理搜索结果时出错: {str(e)}")
                        continue
                
                self.db.save_progress(keyword, engine_name, current_page)
                
                if not engine.next_page():
                    break
                    
                current_page += 1
                logger.info(f"进入第 {current_page} 页")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"处理关键词时出错: {str(e)}")
        finally:
            self.db.save_progress(keyword, engine_name, current_page)

    def run(self):
        """运行主程序"""
        try:
            for keyword in self.config['keywords']:
                for engine_name in self.engines:
                    self.process_keyword(engine_name, keyword)
        finally:
            self.browser_manager.quit()  # 使用 browser_manager 来关闭浏览器 