import yaml
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import sqlite3

logger = logging.getLogger(__name__)

class SearchEngine(ABC):
    def __init__(self, config_path: str, browser_manager):
        """初始化搜索引擎"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.browser_manager = browser_manager
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait
        self.cookies_loaded = False
        self.db_conn = sqlite3.connect(self.config['database']['path'])

    @abstractmethod
    def search(self, keyword: str) -> None:
        """执行搜索"""
        pass

    @abstractmethod
    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果"""
        pass

    @abstractmethod
    def check_expired(self, url: str) -> bool:
        """检查链接是否过期"""
        pass

    @abstractmethod
    def submit_feedback(self, result: Dict[str, Any]) -> None:
        """提交反馈"""
        pass

    @abstractmethod
    def next_page(self) -> bool:
        """跳转到下一页，返回是否存在下一页"""
        pass

    def is_page_expired(self, content: str) -> bool:
        """检查页面内容是否符合过期条件"""
        expired_texts = self.config['expired_conditions']['texts']
        # 将页面内容转换为小写以进行不区分大小写的匹配
        content_lower = content.lower()
        # 使用模糊匹配，不区分大小写
        return any(text.strip().lower() in content_lower for text in expired_texts)

    def wait_for_redirect(self, timeout: int = 5) -> bool:
        """等待并检查是否发生重定向"""
        start_url = self.driver.current_url
        time.sleep(timeout)
        return self.driver.current_url != start_url 

    def ensure_browser(self):
        """确保浏览器正常"""
        if not self.browser_manager.check_browser():
            self.driver = self.browser_manager.driver
            self.wait = self.browser_manager.wait
            return False
        return True 

    def wait_for_feedback_completion(self):
        """等待反馈提交完成"""
        raise NotImplementedError("子类必须实现 wait_for_feedback_completion 方法") 

    def process_pages(self, keyword: str) -> None:
        """处理所有搜索页面，包括动态加载的新页面"""
        try:
            # 执行搜索
            self.search(keyword)
            processed_pages = set()  # 记录已处理的页码
            
            while True:
                # 获取当前页码
                current_page = self.get_current_page()
                if current_page in processed_pages:
                    logger.info(f"页面 {current_page} 已处理过，停止搜索")
                    break
                
                # 处理当前页的搜索结果
                results = self.get_search_results()
                self.process_search_results(results)
                processed_pages.add(current_page)
                
                # 检查是否有下一页
                if not self.next_page():
                    logger.info("没有更多页面")
                    break
                    
                time.sleep(2)  # 等待页面加载
                
        except Exception as e:
            logger.error(f"处理搜索页面时出错: {str(e)}")
    
    @abstractmethod
    def get_current_page(self) -> int:
        """获取当前页码"""
        pass 

    def ensure_login(self) -> bool:
        """确保登录状态"""
        try:
            # 先尝试加载本地 cookies
            if not self.cookies_loaded:
                domain = self.get_domain()
                if self.browser_manager.load_cookies(domain):
                    logger.info(f"已加载 {domain} 的本地 cookies")
                    self.cookies_loaded = True
                    # 刷新页面使 cookies 生效
                    self.driver.refresh()
                    time.sleep(2)

            # 检查登录状态
            if self.check_login():
                logger.info("登录状态检查：已登录")
                return True

            # 需要登录，等待手动登录
            logger.info("检测到需要登录，请在浏览器中完成登录...")
            while not self.check_login():
                time.sleep(2)
                if not self.ensure_browser():
                    return False

            # 登录成功，保存新的 cookies
            logger.info("登录成功，保存 cookies")
            self.browser_manager.save_cookies(self.get_domain())
            return True

        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            return False

    @abstractmethod
    def check_login(self) -> bool:
        """检查是否已登录"""
        pass

    @abstractmethod
    def get_domain(self) -> str:
        """获取搜索引擎域名"""
        pass 

    def process_search_results(self, results: List[Dict[str, Any]]) -> None:
        """处理搜索结果"""
        for index, result in enumerate(results, 1):
            try:
                logger.info(f"检查第 {index} 条结果: {result['title']}")
                logger.info(f"URL: {result['url']}")
                
                # 先查询数据库中是否有记录
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "SELECT is_expired FROM results WHERE url = ?", 
                    (result['url'],)
                )
                record = cursor.fetchone()
                
                if record is not None:
                    # 如果有记录，直接使用数据库中的结果
                    is_expired = bool(record[0])
                    logger.info(f"使用数据库记录 - 链接状态: {'已过期' if is_expired else '正常'}")
                    
                    if is_expired:
                        logger.info("跳过已反馈的过期链接")
                    continue
                
                # 如果没有记录，则检查链接
                is_expired = self.check_expired(result['url'])
                logger.info(f"检查结果: {'已过期' if is_expired else '正常'}")
                
                # 将结果保存到数据库
                cursor.execute(
                    """
                    INSERT INTO results (url, is_expired, check_time, engine)
                    VALUES (?, ?, datetime('now'), ?)
                    """,
                    (result['url'], is_expired, self.get_domain())
                )
                self.db_conn.commit()
                
                if is_expired:
                    logger.info(f"发现过期链接，准备提交反馈: {result['url']}")
                    if self.submit_feedback(result):
                        logger.info("反馈提交成功")
                    else:
                        logger.error("反馈提交失败")
                        return  # 如果反馈提交失败，停止处理后续结果
                
            except Exception as e:
                logger.error(f"处理搜索结果时出错: {str(e)}")
                return  # 出错时停止处理后续结果 