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
            
            # 检查数据库中是否已存在相同的title+url且已过期的记录
            # 如果存在且is_expired=1，说明已经处理过反馈，直接跳过
            existing_expired_record = self.db.get_existing_result(None, keyword, engine_name, result['title'])
            if existing_expired_record and existing_expired_record.get('is_expired'):
                logger.info(f"【{browser_info}】该链接已存在过期记录，跳过反馈: {engine_name} - {result['title']}")
                print(f"该链接已存在过期记录，跳过反馈: {engine_name} - {result['title']}")
                return True
            
            # 检查search_engine+url是否已存在
            engine_url_exists = self.db.get_existing_result(url=result['url'], search_engine=engine_name)
            if engine_url_exists and engine_url_exists.get('is_expired'):
                logger.info(f"【{browser_info}】该URL已存在过期记录，跳过反馈: {engine_name} - {result['url']}")
                print(f"该URL已存在过期记录，跳过反馈: {engine_name} - {result['url']}")
                return True
            elif engine_url_exists:
                logger.info(f"【{browser_info}】该URL已存在但未过期，跳过处理: {engine_name} - {result['url']}")
                print(f"该URL已存在但未过期，跳过处理: {engine_name} - {result['url']}")
                return True
            
            # 检查是否过期
            logger.info(f"【{browser_info}】过期检测：{engine_name} - {keyword} - {result['title']}")
            is_expired = engine.check_expired(result['url'])
            result['is_expired'] = is_expired
            
            # 提交反馈
            if is_expired:
                logger.info(f"【{browser_info}】发现过期链接：{engine_name} - {keyword} - {result['title']}")
                feedback_success = engine.submit_feedback(result)
                
                if not feedback_success:
                    logger.error(f"【{browser_info}】反馈提交失败：{engine_name} - {keyword} - {result['title']}")
                    print(f"反馈提交失败：{engine_name} - {keyword} - {result['title']}")
                    
                    # 即使反馈失败也要保存记录，标记为过期，下次启动时会跳过
                    self.db.save_result(result)
                    logger.info(f"【{browser_info}】已保存过期记录，下次启动时会跳过：{result['url']}")
                    
                    print("检测到反馈失败，自动重启程序……")
                    logger.error("检测到反馈失败，自动重启程序……")
                    python = sys.executable
                    os.execv(python, [python] + sys.argv)
                    return True
                else:
                    logger.info(f"【{browser_info}】反馈提交成功：{engine_name} - {keyword} - {result['title']}")
                    print(f"反馈提交成功：{engine_name} - {keyword} - {result['title']}")
                
                # 无论反馈成功还是失败都保存结果
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
        
        # 关键词异常计数器
        retry_key = f"{engine_name}::{keyword}"
        if not hasattr(self, '_keyword_retry_count'):
            self._keyword_retry_count = {}
        if retry_key not in self._keyword_retry_count:
            self._keyword_retry_count[retry_key] = 0
        
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
                    break
                    
                for result in results:
                    result['keyword'] = keyword
                    result['search_engine'] = engine_name
                    # 处理单个结果
                    if not self.process_single_result(engine, result, keyword, engine_name):
                        logger.info(f"【{browser_info}】处理中断: {engine_name} - {keyword}")
                        # 异常计数+1
                        self._keyword_retry_count[retry_key] += 1
                        if self._keyword_retry_count[retry_key] >= 10:
                            logger.info(f"【{browser_info}】关键词异常/重启次数已达上限，强制标记为已完成: {engine_name} - {keyword}")
                            self.db.save_progress(keyword, engine_name, is_done=True)
                        return
                        
                if not engine.next_page():
                    logger.info(f"【{browser_info}】已到最后一页，关键词完成: {engine_name} - {keyword}")
                    break
                
                current_page += 1
                
                if current_page > Limit:
                    logger.info(f"【{browser_info}】已处理到第 {current_page} 页，关键词完成: {engine_name} - {keyword}")
                    break

                time.sleep(1)  # 翻页后等待加载
            # 只有所有流程顺利跑完才写入完成状态
            self.db.save_progress(keyword, engine_name, is_done=True)
        except Exception as e:
            logger.error(f"【{browser_info}】处理关键词出错: {keyword} - {str(e)}")
            # 异常计数+1
            self._keyword_retry_count[retry_key] += 1
            if self._keyword_retry_count[retry_key] >= 10:
                logger.info(f"【{browser_info}】关键词异常/重启次数已达上限，强制标记为已完成: {engine_name} - {keyword}")
                self.db.save_progress(keyword, engine_name, is_done=True)

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