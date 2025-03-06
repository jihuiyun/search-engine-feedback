from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base import SearchEngine
import time
import logging
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select

logger = logging.getLogger(__name__)

class SogouEngine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['sogou']
        self.feedback_config = self.config['feedback']

    def search(self, keyword: str) -> None:
        """执行搜狗搜索"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器状态: 已重新初始化")
            
            # 访问搜索页面
            self.driver.get(self.engine_config['url'])
            time.sleep(2)
            
            # 查找搜索输入框
            search_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "query"))
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
                EC.presence_of_element_located((By.CLASS_NAME, "results"))
            )
            
            # 获取所有搜索结果
            result_items = self.driver.find_elements(By.CLASS_NAME, "vrwrap")
            
            for item in result_items:
                try:
                    # 获取标题和链接
                    title_element = item.find_element(By.CLASS_NAME, "vr-title")
                    link = title_element.find_element(By.TAG_NAME, "a")
                    
                    # 获取标题
                    title = link.text.strip()
                    
                    # 检查标题是否重复
                    if any(r['title'] == title for r in results):
                        logger.debug(f"跳过重复标题: {title}")
                        continue
                    
                    url = link.get_attribute('href')
                    
                    result = {
                        'title': title,
                        'url': url,
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
            if self.is_page_expired():
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
        if not self.ensure_browser():
            return False
        
        current_window = self.driver.current_window_handle
        
        try:
            # 在新标签页打开反馈页面
            self.driver.execute_script(f"window.open('{self.engine_config['feedback_url']}', '_blank');")
            time.sleep(1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载
            time.sleep(2)
            
            # 选择"删除快照"选项
            delete_option = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='删除快照']"))
            )
            delete_option.click()
            
            # 填写快照地址
            url_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "url"))
            )
            url_input.clear()
            url_input.send_keys(result['url'])
            
            # 填写详细描述
            description = self.wait.until(
                EC.presence_of_element_located((By.NAME, "description"))
            )
            description.clear()
            description.send_keys(self.feedback_config['description'])

            # 选择申请人类型为"单位/公司"
            applicant_type = Select(self.wait.until(
                EC.presence_of_element_located((By.NAME, "applicant_type"))
            ))
            applicant_type.select_by_visible_text("单位/公司")

            # 上传有效资料
            for image_path in self.engine_config['qualification_images']:
                full_path = os.path.join(self.config['qualification_dir'], image_path)
                if os.path.exists(full_path):
                    file_input = self.wait.until(
                        EC.presence_of_element_located((By.NAME, "file"))
                    )
                    file_input.send_keys(full_path)
                    time.sleep(1)  # 等待上传完成
            
            # 填写邮箱
            email_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.clear()
            email_input.send_keys(self.feedback_config['email'])
            
            # 等待用户完成验证码验证
            try:
                # 创建一个新的 WebDriverWait 实例，设置超时时间为 30 分钟
                long_wait = WebDriverWait(self.driver, 1800)  # 30分钟 = 1800秒
                long_wait.until(
                    lambda driver: driver.find_element(
                        By.CSS_SELECTOR, 
                        "div.success-message"
                    ).is_displayed()
                )
            except TimeoutException:
                logger.error("等待验证码验证超时(30分钟)")
                return False
            
            # 提交表单
            submit_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '提交')]"))
            )
            submit_button.click()
            
            # 等待提交完成
            time.sleep(2)
            
            logger.info(f"成功提交反馈: {result['url']}")
            return True
            
        except Exception as e:
            logger.error(f"提交反馈失败: {str(e)}")
            return False
            
        finally:
            # 关闭反馈标签页，切回原标签页
            self.driver.close()
            self.driver.switch_to.window(current_window)
            time.sleep(1)

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_link = self.wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "下一页"))
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
                    By.CSS_SELECTOR,
                    "div.success-message"
                ))
            )
            # 等待反馈成功提示消失
            self.wait.until(
                EC.invisibility_of_element(success_element)
            )
        except TimeoutException:
            logger.warning("等待搜狗搜索反馈完成超时")

    def get_current_page(self) -> int:
        """获取搜狗搜索当前页码"""
        try:
            # 查找当前页码元素
            current = self.driver.find_element(By.CSS_SELECTOR, "div.pagination strong")
            return int(current.text)
        except (NoSuchElementException, ValueError):
            return 1

    def get_domain(self) -> str:
        return "sogou.com"

    def check_login(self) -> bool:
        """搜狗搜索不需要登录"""
        return True 