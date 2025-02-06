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
        current_page = self.db.get_progress(keyword, engine_name)
        is_completed = False
        logger.info(f"任务开始: {engine_name} 引擎搜索 '{keyword}'，从第 {current_page} 页继续")
        
        try:
            engine.search(keyword)
            while True:
                results = engine.get_search_results()
                
                if not results:
                    logger.info(f"任务完成: {engine_name} 搜索 '{keyword}' 的当前页 {current_page} 超过最大页数")
                    self.db.save_progress(
                        keyword, 
                        engine_name, 
                        current_page,
                        is_done=True
                    )
                    is_completed = True
                    return
                
                logger.info(f"搜索结果: 第 {current_page} 页获取到 {len(results)} 条记录")
                
                for index, result in enumerate(results, 1):
                    try:
                        # 添加关键词和搜索引擎信息
                        result['keyword'] = keyword
                        result['search_engine'] = engine_name
                        
                        logger.info(f"处理结果: 第 {current_page} 页第 {index} 条 - {result['title']}")
                        logger.debug(f"URL: {result['url']}")
                        
                        # 检查 URL 是否已处理过
                        existing_result = self.db.get_existing_result(result['url'])
                        if existing_result:
                            logger.info(f"URL已处理: {result['url']}")
                            # 如果关键词或标题不同，则保存新记录
                            if (existing_result['keyword'] != keyword or 
                                existing_result['title'] != result['title']):
                                result['is_expired'] = existing_result['is_expired']  # 使用已存在记录的过期状态
                                self.db.save_result(result)
                                logger.info("保存新的关联记录")
                            continue
                        
                        # 检查链接是否过期
                        is_expired = engine.check_expired(result['url'])
                        result['is_expired'] = is_expired
                        status = "已过期" if is_expired else "正常"
                        logger.info(f"链接状态: {status}")
                        
                        # 保存结果
                        self.db.save_result(result)
                        
                        if is_expired:
                            logger.info(f"提交反馈: 准备处理过期链接...")
                            engine.submit_feedback(result)
                            logger.info("反馈完成: 已提交处理请求")
                            
                    except Exception as e:
                        logger.error(f"处理错误: 第 {current_page} 页第 {index} 条结果处理失败 - {str(e)}")
                        continue
                
                # 尝试翻页
                if not engine.next_page():
                    logger.info(f"任务完成: {engine_name} 搜索 '{keyword}' 已到达最后一页")
                    self.db.save_progress(
                        keyword, 
                        engine_name, 
                        current_page,
                        is_done=True
                    )
                    is_completed = True
                    break
                
                current_page += 1
                logger.info(f"进入第 {current_page} 页")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"处理关键词时出错: {str(e)}")
        finally:
            # 只有在任务未正常完成时才保存进度且不标记完成
            if not is_completed:
                logger.debug(f"保存未完成进度: {engine_name} 搜索 '{keyword}' 停在第 {current_page} 页")
                self.db.save_progress(keyword, engine_name, current_page, is_done=False)

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