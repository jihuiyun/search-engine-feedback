import yaml
import logging
import time
from typing import Dict
from selenium.webdriver.remote.webdriver import WebDriver
from src.database import Database
from src.engines.base import SearchEngine
from selenium.webdriver.common.by import By

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
        
        # 检查是否已完成
        if self.db.check_keyword_done(keyword, engine_name):
            logger.info(f"跳过已完成关键词: {engine_name} - {keyword}")
            return
            
        # 确保登录状态
        if not engine.load_cookies_and_login():
            logger.error(f"登录失败: {engine_name}")
            return
            
        is_completed = False
        
        try:
            engine.search(keyword)
            while True:
                results = engine.get_search_results()
                
                if not results:
                    logger.info(f"搜索完成: {engine_name} - {keyword}")
                    self.db.save_progress(keyword, engine_name, is_done=True)
                    is_completed = True
                    break
                    
                for result in results:
                    # 添加关键词和搜索引擎信息
                    result['keyword'] = keyword
                    result['search_engine'] = engine_name
                    
                    # 检查是否已处理过
                    existing_result = self.db.get_existing_result(
                        result['url'], 
                        keyword,
                        engine_name
                    )
                    if existing_result:
                        continue
                        
                    # 检查是否过期
                    is_expired = engine.check_expired(result['url'])
                    result['is_expired'] = is_expired
                    
                    # 保存结果
                    self.db.save_result(result)
                    
                    # 提交反馈
                    if is_expired:
                        if not engine.submit_feedback(result):
                            logger.error("反馈提交失败")
                            return
                            
                # 保存当前进度
                self.db.save_progress(keyword, engine_name, is_done=False)
                
                # 尝试下一页
                if not engine.next_page():
                    logger.info(f"已到最后一页: {engine_name} - {keyword}")
                    self.db.save_progress(keyword, engine_name, is_done=True)
                    is_completed = True
                    break
                    
                time.sleep(2)  # 翻页后等待加载
                
        except Exception as e:
            logger.error(f"处理关键词出错: {str(e)}")
        finally:
            if not is_completed:
                self.db.save_progress(keyword, engine_name, is_done=False)

    def run(self):
        """运行主程序"""
        try:
            for engine_name in self.engines:
                logger.info(f"开始处理 {engine_name} 引擎的搜索任务")
                for keyword in self.config['keywords']:
                    # 检查关键词是否已完成
                    is_done = self.db.check_keyword_done(keyword, engine_name)
                    if is_done:
                        logger.info(f"跳过已完成关键词: {engine_name} 搜索 '{keyword}'")
                        continue
                        
                    self.process_keyword(engine_name, keyword)
                logger.info(f"完成 {engine_name} 引擎的所有关键词处理")
        finally:
            self.browser_manager.quit() 