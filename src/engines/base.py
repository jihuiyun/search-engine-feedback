import yaml
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

class SearchEngine(ABC):
    def __init__(self, config_path: str, browser_manager):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.browser_manager = browser_manager
        self.driver = browser_manager.driver
        self.wait = browser_manager.wait

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