from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base import SearchEngine
import time
import logging
import os

logger = logging.getLogger(__name__)

class So360Engine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['so360']
        self.feedback_config = self.config['feedback']

    def search(self, keyword: str) -> None:
        """执行360搜索"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器状态: 已重新初始化")
            
            # 访问搜索页面
            self.driver.get(self.engine_config['url'])
            time.sleep(2)
            
            # 查找搜索输入框
            search_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "input"))
            )
            search_input.clear()
            search_input.send_keys(keyword)
            search_input.send_keys(Keys.RETURN)
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"搜索错误: {str(e)}")

    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果列表"""
        results = []
        try:
            # 等待搜索结果加载
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "res-list"))
            )
            
            # 获取所有搜索结果
            result_items = self.driver.find_elements(By.CLASS_NAME, "res-list")
            
            for item in result_items:
                try:
                    # 获取标题和链接
                    title_element = item.find_element(By.CLASS_NAME, "res-title")
                    link = title_element.find_element(By.TAG_NAME, "a")
                    
                    result = {
                        'title': link.text.strip(),
                        'url': link.get_attribute('href'),
                        'element': item
                    }
                    results.append(result)
                    
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            logger.error(f"获取搜索结果失败: {str(e)}")
            
        return results

    def check_expired(self, url: str) -> bool:
        """检查链接是否过期"""
        if not self.ensure_browser():
            return False
            
        current_window = self.driver.current_window_handle
        
        try:
            # 新标签页打开链接
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            time.sleep(1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载
            time.sleep(2)
            
            # 检查页面内容
            page_content = self.driver.page_source
            if self.is_page_expired(page_content):
                logger.info("检测到页面包含过期标志")
                return True
            
            # 检查重定向
            if self.wait_for_redirect(self.config['expired_conditions']['redirect_timeout']):
                logger.info("检测到页面发生重定向")
                return True
            
            logger.info("页面正常访问")
            return False
            
        finally:
            self.driver.close()
            self.driver.switch_to.window(current_window)
            time.sleep(1)

    def submit_feedback(self, result: Dict[str, Any]) -> bool:
        """提交反馈"""
        try:
            # 打开反馈页面
            self.driver.get(self.engine_config['feedback_url'])
            time.sleep(2)
            
            # 填写反馈表单
            # TODO: 实现360搜索的具体反馈流程
            logger.warning("360搜索的反馈功能尚未实现")
            return False
            
        except Exception as e:
            logger.error(f"提交反馈失败: {str(e)}")
            return False

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_link = self.wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "next"))
            )
            
            if not next_link:
                return False
            
            # 点击下一页
            next_link.click()
            time.sleep(2)
            
            return True
            
        except (NoSuchElementException, TimeoutException):
            return False

    def wait_for_feedback_completion(self):
        """等待反馈提交完成"""
        try:
            # 等待反馈成功提示元素出现
            success_element = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    self.config['selectors']['so']['feedback_success']
                ))
            )
            # 等待反馈成功提示消失
            self.wait.until(
                EC.invisibility_of_element(success_element)
            )
        except TimeoutException:
            logger.warning("等待360搜索反馈完成超时")

    def get_current_page(self) -> int:
        """获取360搜索当前页码"""
        try:
            # 查找当前页码元素
            current = self.driver.find_element(By.CSS_SELECTOR, "li.active span")
            return int(current.text)
        except (NoSuchElementException, ValueError):
            return 1

    def get_domain(self) -> str:
        return "so.com"

    def check_login(self) -> bool:
        try:
            # 检查登录状态的元素
            login_btn = self.driver.find_elements(By.CLASS_NAME, "login-btn")
            return not (login_btn and login_btn[0].is_displayed())
        except Exception:
            return False 