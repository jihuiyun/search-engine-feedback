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
import re

logger = logging.getLogger(__name__)

class BingEngine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['bing']
        self.feedback_config = self.config['feedback']
        self.daily_feedback_count = 0
        self.max_daily_feedback = 10

    def search(self, keyword: str, target_page: int = None) -> None:
        """执行必应搜索，支持直接跳转到指定页码"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器状态: 已重新初始化")
            
            logger.info(f"执行搜索: '{keyword}'")
            
            if target_page and target_page > 1:
                # 直接构造目标页的URL
                first_param = (target_page - 1) * 10
                search_url = f"{self.engine_config['url']}search?q={keyword}&first={first_param}"
                logger.info(f"直接跳转到第 {target_page} 页")
            else:
                search_url = self.engine_config['url']
            
            self.driver.get(search_url)
            time.sleep(2)

            if not target_page:
                # 如果不是直接跳转，需要执行搜索
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "sb_form_q"))
                )
                search_input.clear()
                search_input.send_keys(keyword)
                search_input.send_keys(Keys.RETURN)
                logger.debug("搜索请求: 已提交")
                time.sleep(2)
            
        except Exception as e:
            logger.error(f"搜索错误: {str(e)}")

    def get_page_info(self) -> Dict[str, int]:
        """获取当前页码信息"""
        try:
            page_info = {'current': 1, 'max': 1}
            
            # 获取所有页码按钮（排除下一页按钮）
            page_links = self.driver.find_elements(By.CSS_SELECTOR, "li a[aria-label^='第']")
            if page_links:
                # 获取当前页码
                current_page_elem = self.driver.find_element(By.CSS_SELECTOR, "li a.sb_pagS")
                page_info['current'] = int(current_page_elem.text)
                
                # 获取最大页码
                page_info['max'] = max(int(link.text) for link in page_links)
                
            return page_info
        except Exception as e:
            logger.error(f"获取页码信息失败: {str(e)}")
            return {'current': 1, 'max': 1}

    def get_search_results(self, target_page: int = None) -> List[Dict[str, Any]]:
        """获取搜索结果列表，支持处理目标页码"""
        results = []
        try:
            if not self.ensure_browser():
                logger.error("浏览器状态: 连接已断开，尝试重新初始化")
                return results
            
            # 等待搜索结果加载
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, "b_results")))
            except TimeoutException:
                logger.error("搜索结果: 加载超时")
                return results
            
            # 检查是否有搜索结果
            try:
                # 检查是否显示"没有找到结果"
                no_results = self.driver.find_elements(By.CLASS_NAME, "b_no")
                if no_results:
                    logger.info("搜索结果: 没有找到相关结果")
                    return results
                
                # 获取页码信息
                page_info = self.get_page_info()
                logger.debug(f"页码信息: 当前第 {page_info['current']} 页，最大 {page_info['max']} 页")
                
                if target_page:
                    if target_page > page_info['max']:
                        logger.warning(f"目标页码 {target_page} 超过最大页数 {page_info['max']}")
                        return results
                    elif target_page != page_info['current']:
                        logger.info(f"当前在第 {page_info['current']} 页，需要跳转到第 {target_page} 页")
                        self.search(self.current_keyword, target_page)
                        return self.get_search_results()  # 递归获取目标页结果
                
                # 获取搜索结果
                result_items = self.driver.find_elements(By.CLASS_NAME, "b_algo")
                if not result_items:
                    logger.warning("搜索结果: 未找到任何结果")
                    return results
                
                logger.info(f"搜索结果: 找到 {len(result_items)} 条记录")
                
                for item in result_items:
                    try:
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
                logger.error(f"搜索结果处理错误: {str(e)}")
            
        except Exception as e:
            logger.error(f"获取搜索结果失败: {str(e)}")
            if "Connection refused" in str(e):
                logger.warning("浏览器连接断开，尝试重新初始化...")
                self.ensure_browser()
        
        return results

    def check_expired(self, url: str) -> bool:
        """检查链接是否过期"""
        logger.debug(f"开始检查: {url}")
        try:
            # 设置超时
            self.driver.set_page_load_timeout(5)
            logger.debug("页面加载: 设置5秒超时")
            
            # 新标签页打开
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            try:
                time.sleep(2)
                page_content = self.driver.page_source
                if self.is_page_expired(page_content):
                    logger.info("检查结果: 页面包含过期标志")
                    return True
                
                logger.debug("检查重定向: 等待页面状态...")
                if self.wait_for_redirect(self.config['expired_conditions']['redirect_timeout']):
                    logger.info("检查结果: 检测到页面重定向")
                    return True
                
                logger.info("检查结果: 页面正常访问")
                return False
                
            except TimeoutException:
                logger.info("检查结果: 页面加载超时，视为正常")
                return False
                
        finally:
            # 恢复默认超时设置
            self.driver.set_page_load_timeout(300)  # 恢复默认的300秒
            # 关闭当前标签页,切回原标签页
            try:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception as e:
                logger.error(f"关闭标签页失败: {str(e)}")
                # 如果关闭失败，尝试重新初始化浏览器
                self.ensure_browser()

    def submit_feedback(self, result: Dict[str, Any]) -> bool:
        if self.daily_feedback_count >= self.max_daily_feedback:
            logger.warning("今日反馈次数已达上限，请更换账号")
            input("请更换账号并登录后按回车继续...")
            self.daily_feedback_count = 0
            self.cookies_loaded = False
            
        success = super().submit_feedback(result)
        if success:
            self.daily_feedback_count += 1
        return success

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 获取所有页码，检查最大页数
            page_links = self.driver.find_elements(By.CSS_SELECTOR, "li a.b_widePag")
            if page_links:
                page_numbers = [int(link.text) for link in page_links if link.text.isdigit()]
                if page_numbers:
                    max_page = max(page_numbers)
                    current_url = self.driver.current_url
                    current_page_match = re.search(r'first=(\d+)', current_url)
                    current_page = 1
                    if current_page_match:
                        current_page = (int(current_page_match.group(1)) // 10) + 1
                    if current_page >= max_page:
                        logger.info(f"已到达最后一页: {max_page}")
                        return False
            
            # 查找下一页按钮
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
            
            # 直接使用URL导航
            self.driver.get(next_url)
            time.sleep(2)
            
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

    def get_current_page(self) -> int:
        """获取必应搜索当前页码"""
        try:
            # 从URL中获取页码
            current_url = self.driver.current_url
            if 'first=' in current_url:
                # Bing使用first参数表示结果起始位置，每页10条
                first = int(re.search(r'first=(\d+)', current_url).group(1))
                return (first // 10) + 1
            return 1
        except (AttributeError, ValueError):
            return 1

    def get_domain(self) -> str:
        return "bing.com"

    def check_login(self) -> bool:
        try:
            # 检查当前URL是否是登录页面
            login_urls = [
                "https://www.bing.com/toolbox/intermediatelogin/",
                "https://login.microsoftonline.com/",
                "https://login.live.com/"
            ]
            return not any(self.driver.current_url.startswith(url) for url in login_urls)
        except Exception:
            return False 