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

class BingEngine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['bing']
        self.feedback_config = self.config['feedback']

    def search(self, keyword: str) -> None:
        """执行必应搜索"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器已重新初始化")
            
            # 打开必应搜索页面
            self.driver.get(self.engine_config['url'])
            time.sleep(2)
            
            # 查找搜索框并输入关键词
            search_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "sb_form_q"))
            )
            search_input.clear()
            search_input.send_keys(keyword)
            search_input.send_keys(Keys.RETURN)
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")
            return None

    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果列表"""
        results = []
        try:
            # 等待搜索结果加载
            self.wait.until(
                EC.presence_of_element_located((By.ID, "b_results"))
            )
            
            # 获取所有搜索结果
            result_items = self.driver.find_elements(By.CLASS_NAME, "b_algo")
            
            for item in result_items:
                try:
                    # 获取标题和链接
                    title_element = item.find_element(By.TAG_NAME, "h2").find_element(By.TAG_NAME, "a")
                    
                    result = {
                        'title': title_element.text.strip(),
                        'url': title_element.get_attribute('href'),
                        'element': item
                    }
                    results.append(result)
                    
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            logger.error(f"获取搜索结果出错: {str(e)}")
            
        return results

    def check_expired(self, url: str) -> bool:
        """检查链接是否过期"""
        if not self.ensure_browser():
            return False
            
        current_window = self.driver.current_window_handle
        
        try:
            # 新标签页打开链接
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载
            time.sleep(2)
            
            # 检查是否重定向到首页
            if self.wait_for_redirect(self.config['expired_conditions']['redirect_timeout']):
                return True
                
            # 检查页面内容是否包含过期标志
            page_content = self.driver.page_source
            is_expired = self.is_page_expired(page_content)
            
            return is_expired
            
        finally:
            # 关闭当前标签页,切回原标签页
            self.driver.close()
            self.driver.switch_to.window(current_window)

    def submit_feedback(self, result: Dict[str, Any]) -> None:
        """提交反馈"""
        try:
            # 打开反馈页面
            feedback_url = self.engine_config['feedback_url']
            self.driver.get(feedback_url)
            time.sleep(2)
            
            # 尝试加载已保存的 cookies
            if self.browser_manager.load_cookies('bing.com'):
                # 重新加载页面以应用 cookies
                self.driver.get(feedback_url)
                time.sleep(2)
            
            # 检查是否需要登录 - 支持多个登录页面
            login_urls = [
                "https://www.bing.com/toolbox/intermediatelogin/",
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                "https://login.live.com/"
            ]
            
            # 检查当前URL是否是登录页面
            is_login_page = any(self.driver.current_url.startswith(url) for url in login_urls)
            if is_login_page:
                logger.info("检测到需要登录，等待手动登录...")
                # 等待用户手动登录完成，通过检查URL变化来判断
                while any(self.driver.current_url.startswith(url) for url in login_urls):
                    time.sleep(1)
                logger.info("登录完成，继续提交反馈")
                # 保存登录后的 cookies
                self.browser_manager.save_cookies('bing.com')
                time.sleep(2)
            
            # 确保在反馈页面
            if not self.driver.current_url.startswith(feedback_url):
                logger.info("重新导航到反馈页面")
                self.driver.get(feedback_url)
                time.sleep(2)
            
            # 等待并填写内容URL输入框
            url_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='输入 URL 或粘贴复制的 URL']"))
            )
            url_input.clear()
            url_input.send_keys(result['url'])
            logger.info(f"已填写URL: {result['url']}")
            
            # 选择"删除页面"选项
            delete_page_radio = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ChoiceGroup11']+label"))
            )
            delete_page_radio.click()
            logger.info("已选择'删除页面'选项")
            
            # 点击提交按钮 - 使用中文文本定位
            submit_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//*[text()='提交']"))
            )
            self.driver.execute_script("arguments[0].click();", submit_btn)  # 使用 JavaScript 点击
            logger.info("已点击提交按钮")
            
            time.sleep(2)  # 等待提交完成
            
        except Exception as e:
            logger.error(f"提交反馈失败: {str(e)}")
            # 保存错误截图和页面源码到错误日志目录
            try:
                timestamp = int(time.time())
                error_prefix = f"bing_feedback_error_{timestamp}"
                
                # 保存截图
                screenshot_path = os.path.join(
                    self.browser_manager.error_logs_dir, 
                    f"{error_prefix}.png"
                )
                self.driver.save_screenshot(screenshot_path)
                logger.error(f"错误截图已保存到: {screenshot_path}")
                
                # 保存页面源码
                html_path = os.path.join(
                    self.browser_manager.error_logs_dir,
                    f"{error_prefix}.html"
                )
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                logger.error(f"页面源码已保存到: {html_path}")
            except:
                pass

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_link = self.driver.find_element(By.CLASS_NAME, "sb_pagN")
            
            if not next_link:
                return False
            
            # 点击下一页
            next_link.click()
            time.sleep(2)
            
            return True
            
        except NoSuchElementException:
            return False 