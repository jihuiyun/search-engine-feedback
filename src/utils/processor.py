import yaml
import logging
import time
from typing import Dict, Any
from selenium.webdriver.remote.webdriver import WebDriver
from src.database import Database
from src.engines.base import SearchEngine
from selenium.webdriver.common.by import By
import sys
import os

logger = logging.getLogger(__name__)

class SearchProcessor: # 搜索处理器
    def __init__(self, config_path: str, browser_manager, engines: Dict[str, SearchEngine]):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.browser_manager = browser_manager # 浏览器管理器   
        self.driver = browser_manager.driver # 浏览器驱动
        self.engines = engines # 搜索引擎
        # 初始化数据库
        self.db = Database(self.config['database'])

    def highlight_result(self, result: Dict[str, Any], highlight: bool = True):
        """高亮或取消高亮搜索结果"""
        if 'element' not in result:
            return
        
        color = '#ff977c' if highlight else 'transparent'
        try:
            self.driver.execute_script("""
                arguments[0].style.backgroundColor = arguments[1];
                if (arguments[1] !== 'transparent') {
                    arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
                }
            """, result['element'], color)
            if highlight:
                time.sleep(1)  # 等待滚动和高亮效果
        except Exception as e:
            logger.error(f"{'高亮' if highlight else '取消高亮'}搜索结果失败: {str(e)}")

    def process_single_result(self, engine: SearchEngine, result: Dict[str, Any], keyword: str, engine_name: str) -> bool:
        """处理单个搜索结果"""
        browser_info = self.browser_manager.get_browser_info() if hasattr(self.browser_manager, 'get_browser_info') else "默认浏览器"
        
        try:
            # 高亮当前处理的结果
            self.highlight_result(result, True)
            
            # 新增：如果数据库已存在该search_engine+url，直接跳过后续所有处理，保证search_engine+url唯一
            engine_url_exists = self.db.get_existing_result(url=result['url'], search_engine=engine_name)
            if engine_url_exists:
                logger.info(f"【{browser_info}】search_engine+url已存在数据库，跳过所有处理: {engine_name} - {result['url']}")
                print(f"search_engine+url已存在数据库，跳过所有处理: {engine_name} - {result['url']}")
                return True
            
            # 检查是否已处理过
            existing_result = self.db.get_existing_result(result['url'])
            same = self.db.get_existing_result(None, keyword, engine_name, result['title'])
            
            # if existing_result or same: # 如果已处理过
            #     if not same: # 如果已处理过，但不是同一个关键词，则更新is_expired
            #         result['is_expired'] = existing_result['is_expired']
            #         self.db.save_result(result)
                    
            #     logger.info(f"【{browser_info}】重复，跳过：{engine_name} - {keyword} - {result['title']}")
            #     print(f"【{browser_info}】重复，跳过：{engine_name} - {keyword} - {result['title']}")
            #     return True
                
            # 检查是否过期
            logger.info(f"【{browser_info}】过期检测：{engine_name} - {keyword} - {result['title']}")
            is_expired = engine.check_expired(result['url'])
            result['is_expired'] = is_expired
            
            # 提交反馈
            if is_expired:
                logger.info(f"【{browser_info}】发现过期链接：{engine_name} - {keyword} - {result['title']}")
                if not engine.submit_feedback(result):
                    logger.error(f"【{browser_info}】反馈提交失败：{engine_name} - {keyword} - {result['title']}")
                    print(f"反馈提交失败：{engine_name} - {keyword} - {result['title']}")
                    print("检测到反馈失败，自动重启程序……")
                    logger.error("检测到反馈失败，自动重启程序……")
                    python = sys.executable
                    os.execv(python, [python] + sys.argv)
                    return True
                else:
                    logger.info(f"【{browser_info}】反馈提交成功：{engine_name} - {keyword} - {result['title']}")
                    print(f"反馈提交成功：{engine_name} - {keyword} - {result['title']}")
                # 只有反馈成功才保存结果
                self.db.save_result(result)
            else:
                # 未过期的直接保存
                self.db.save_result(result)
                    
            return True
            
        finally:
            # 取消高亮
            self.highlight_result(result, False)

    def process_keyword(self, engine_name: str, keyword: str): 
        """处理单个关键词"""
        engine = self.engines[engine_name]
        browser_info = self.browser_manager.get_browser_info() if hasattr(self.browser_manager, 'get_browser_info') else "默认浏览器"
        
        # 检查是否已完成
        if self.db.check_keyword_done(keyword, engine_name):
            logger.info(f"【{browser_info}】跳过已完成关键词: {engine_name} - {keyword}")
            print(f"跳过已完成关键词: {engine_name} - {keyword}")
            return
            
        # 确保登录状态
        if not engine.load_cookies_and_login():
            logger.error(f"【{browser_info}】登录失败: {engine_name}")
            return
        # 开始正式检索查询    
        try:
            engine.search(keyword)

            Limit = 20
            current_page = 1
            
            while True:
                results = engine.get_search_results() # 保存当前页检索条目
                
                if not results:
                    logger.info(f"【{browser_info}】搜索完成: {engine_name} - {keyword}")
                    self.db.save_progress(keyword, engine_name, is_done=True)
                    break
                    
                for result in results:
                    # 添加关键词和搜索引擎信息
                    result['keyword'] = keyword
                    result['search_engine'] = engine_name
                    # print(f"处理：{engine_name} - {keyword} - {result['title']}")
                    # 处理单个结果
                    if not self.process_single_result(engine, result, keyword, engine_name):
                        logger.info(f"【{browser_info}】处理中断: {engine_name} - {keyword}")
                        return
                        
                # 尝试下一页
                if not engine.next_page():
                    logger.info(f"【{browser_info}】已到最后一页，关键词完成: {engine_name} - {keyword}")
                    self.db.save_progress(keyword, engine_name, is_done=True)
                    break
                
                current_page += 1
                
                if current_page > Limit:
                    logger.info(f"【{browser_info}】已处理到第 {current_page} 页，关键词完成: {engine_name} - {keyword}")
                    self.db.save_progress(keyword, engine_name, is_done=True)
                    break

                time.sleep(1)  # 翻页后等待加载
                
        except Exception as e:
            logger.error(f"【{browser_info}】处理关键词出错: {keyword} - {str(e)}")

    def run(self):
        """运行主程序"""
        try:
            for engine_name in self.engines:
                browser_info = self.browser_manager.get_browser_info() if hasattr(self.browser_manager, 'get_browser_info') else "默认浏览器"
                logger.info(f"【{browser_info}】开始处理 {engine_name} 引擎的搜索任务")
                for keyword in self.config['keywords']:
                    # 检查关键词是否已完成
                    is_done = self.db.check_keyword_done(keyword, engine_name)
                    if is_done:
                        print(f"【{browser_info}】跳过已完成关键词: {engine_name} 搜索 '{keyword}'")
                        logger.info(f"【{browser_info}】跳过已完成关键词: {engine_name} 搜索 '{keyword}'")
                        continue
                        
                    logger.info(f"【{browser_info}】开始关键词搜索: {engine_name} 搜索 '{keyword}'")
                    print(f"【{browser_info}】开始关键词搜索: {engine_name} 搜索 '{keyword}'")
                    self.process_keyword(engine_name, keyword)
                logger.info(f"【{browser_info}】完成 {engine_name} 引擎的所有关键词处理")
        finally:
            self.browser_manager.quit() 