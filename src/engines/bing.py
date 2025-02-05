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
            # 设置页面加载超时为10秒
            self.driver.set_page_load_timeout(5)  # 改为5秒超时
            
            # 新标签页打开链接
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            try:
                # 等待页面加载
                time.sleep(2)
                
                # 先检查页面内容是否包含过期标志
                page_content = self.driver.page_source
                if self.is_page_expired(page_content):
                    logger.info("检测到页面包含过期标志")
                    return True
                
                # 如果页面内容没有过期标志，则等待看是否会重定向
                logger.info("页面内容正常，等待检查是否重定向...")
                if self.wait_for_redirect(self.config['expired_conditions']['redirect_timeout']):
                    logger.info("检测到页面发生重定向")
                    return True
                
                logger.info("页面正常访问")
                return False
                
            except TimeoutException:
                logger.info(f"页面加载超时: {url}，视为正常页面")
                return False  # 改为将超时视为页面正常
                
        finally:
            # 恢复默认超时设置
            self.driver.set_page_load_timeout(300)  # 恢复默认的300秒
            # 关闭当前标签页,切回原标签页
            try:
                self.driver.close()
                self.driver.switch_to.window(current_window)
            except Exception as e:
                logger.error(f"关闭标签页失败: {str(e)}")
                # 如果关闭失败，尝试重新初始化浏览器
                self.ensure_browser()

    def submit_feedback(self, result: Dict[str, Any]) -> bool:
        """提交反馈"""
        # 保存当前窗口句柄
        current_window = self.driver.current_window_handle
        
        try:
            # 新开标签页
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
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
            # 保存错误截图和页面源码
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
            return False
        
        finally:
            # 关闭反馈标签页，切回搜索结果页
            try:
                self.driver.close()
                self.driver.switch_to.window(current_window)
            except Exception as e:
                logger.error(f"切回原窗口失败: {str(e)}")
                # 如果切回失败，尝试重新初始化浏览器
                self.ensure_browser()
        
        return True

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 使用更精确的选择器查找下一页按钮
            next_link = self.wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    "a.sb_pagN[title='下一页']"
                ))
            )
            
            if not next_link or 'disabled' in next_link.get_attribute('class'):
                return False
            
            # 获取下一页的URL
            next_url = next_link.get_attribute('href')
            if not next_url:
                return False
            
            # 直接使用URL导航而不是点击按钮
            self.driver.get(next_url)
            time.sleep(2)  # 等待页面加载
            
            # 验证是否成功翻页
            try:
                # 检查URL是否包含 first 参数
                current_url = self.driver.current_url
                if 'first=' not in current_url:
                    logger.warning("翻页可能未成功：URL中未找到页码参数")
                    return False
            except Exception as e:
                logger.error(f"验证翻页时出错: {str(e)}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"翻页时出错: {str(e)}")
            return False

    def wait_for_feedback_completion(self):
        """等待反馈提交完成"""
        try:
            # 等待反馈成功提示元素出现
            success_element = WebDriverWait(
                self.driver, 
                self.config['timeouts']['feedback_wait']
            ).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    self.config['selectors']['bing']['feedback_success']
                ))
            )
            # 等待反馈成功提示消失
            WebDriverWait(
                self.driver,
                self.config['timeouts']['feedback_wait']
            ).until(
                EC.invisibility_of_element(success_element)
            )
        except TimeoutException:
            logger.warning("等待必应反馈完成超时") 