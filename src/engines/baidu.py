from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base import SearchEngine
import time
import logging
import os
import json
from selenium.webdriver.support.ui import WebDriverWait
import urllib3

# 设置 urllib3 的日志级别为 ERROR，隐藏连接警告
urllib3.disable_warnings()
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

class BaiduEngine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['baidu']
        self.feedback_config = self.config['feedback']
        self.config_path = config_path

    def _check_and_handle_login(self) -> bool:
        """检查是否需要登录并等待用户登录完成"""
        try:
            # 检查是否存在登录框
            login_popup = self.driver.find_element(By.CLASS_NAME, "passport-login-pop")
            if login_popup.is_displayed():
                return self._wait_for_login()
            return True
        except NoSuchElementException:
            return True

    def search(self, keyword: str) -> None:
        """执行百度搜索"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器已重新初始化")
            
            # 构造搜索 URL
            search_url = f"https://www.baidu.com/s?wd={keyword}"
            
            # 直接访问搜索结果页面
            self.driver.get(search_url)
            time.sleep(1)  # 等待页面加载
            
            # 检查是否需要登录
            if not self._check_and_handle_login():
                logger.error("登录失败")
                return None
            
            # 尝试加载 cookie
            self._load_cookies()
            
            if self.engine_config.get('reload_after_cookie', True):
                # 刷新页面使 cookie 生效
                self.driver.get(search_url)
                time.sleep(1)
                
                # 再次检查登录状态
                if not self._check_and_handle_login():
                    logger.error("登录失败")
                    return None
            
        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")
            return None

    def _load_cookies(self) -> None:
        """加载百度的 cookie"""
        cookie_file = os.path.join(
            os.path.dirname(os.path.dirname(self.config_path)),  # 上级目录
            'cookies',  # cookies 目录
            self.engine_config.get('cookie_file', 'baidu.com.txt')
        )
        
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookie_text = f.read().strip()
                    if cookie_text:
                        cookie_list = [item.strip() for item in cookie_text.split(';') if item.strip()]
                        for cookie_item in cookie_list:
                            name, value = cookie_item.split('=', 1)
                            self.driver.add_cookie({
                                'name': name.strip(),
                                'value': value.strip(),
                                'domain': '.baidu.com'
                            })
                logger.info("成功加载百度 cookie")
            except Exception as e:
                logger.warning(f"加载百度 cookie 失败: {str(e)}")

    def _wait_for_login(self) -> bool:
        """等待用户登录完成"""
        logger.info("检测到需要登录，请在浏览器中完成登录...")
        try:
            while True:
                try:
                    # 检查是否还在登录页面
                    login_popup = self.driver.find_element(By.CLASS_NAME, "passport-login-pop")
                    if login_popup.is_displayed():
                        logger.info("等待用户登录中...")
                        time.sleep(2)
                        continue
                except NoSuchElementException:
                    # 登录框消失，检查是否需要验证
                    try:
                        verify_dialog = self.driver.find_element(By.XPATH, "//div[contains(text(), '验证方式选择')]")
                        if verify_dialog.is_displayed():
                            logger.info("检测到验证页面，请完成验证...")
                            time.sleep(2)
                            continue
                    except NoSuchElementException:
                        pass
                    
                    # 检查是否已登录成功（查找用户头像）
                    try:
                        user_avatar = self.driver.find_element(By.CLASS_NAME, "user-name")
                        if user_avatar.is_displayed():
                            logger.info("登录成功")
                            return True
                    except NoSuchElementException:
                        logger.info("等待登录完成...")
                        time.sleep(2)
                        continue
                
        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            return False

    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果列表"""
        results = []
        try:
            # 等待搜索结果加载
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.result.c-container"))
            )
            time.sleep(1)  # 确保页面稳定
            
            # 获取所有搜索结果，包括普通结果和视频结果
            result_items = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.result.c-container, div.result.c-container.new-pmd"
            )
            
            logger.info(f"找到 {len(result_items)} 个结果项")
            
            for item in result_items:
                try:
                    # 尝试不同的标题选择器
                    title_element = None
                    for selector in ["h3.t a", "h3.c-title a", "h3 a"]:
                        try:
                            title_element = item.find_element(By.CSS_SELECTOR, selector)
                            break
                        except NoSuchElementException:
                            continue
                    
                    if title_element is None:
                        logger.warning(f"无法找到标题元素，跳过此结果项")
                        continue
                    
                    result = {
                        'title': title_element.text.strip(),
                        'url': title_element.get_attribute('href'),
                        'element': item
                    }
                    logger.info(f"成功解析结果: {result['title']}")
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"解析搜索结果项时出错: {str(e)}")
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
            time.sleep(1)  # 等待新标签页打开
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
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
            
        finally:
            # 关闭当前标签页,切回原标签页
            self.driver.close()
            time.sleep(1)  # 等待标签页关闭
            self.driver.switch_to.window(current_window)
            time.sleep(1)  # 等待切换完成

    def submit_feedback(self, result: Dict[str, Any]) -> bool:
        """提交反馈"""
        try:
            # 找到页面底部的反馈按钮
            feedback_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.feedback"))
            )
            feedback_button.click()
            time.sleep(1)

            # 检查是否需要登录，并等待登录完成
            if not self._check_and_handle_login():
                logger.error("登录失败，无法提交反馈")
                return False

            # 重新获取反馈按钮（因为页面可能已经刷新）
            feedback_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.feedback"))
            )
            feedback_button.click()
            time.sleep(1)

            # 填写反馈描述
            description_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea.feedback-content"))
            )
            description_input.clear()
            feedback_text = "网页打不开，提示内容已删除或找不到该网页，请删除快照，且快照包含91y关键词信息为不实内容，误导91y游戏用户，已严重影响到浮云公司的商誉和正常的经营秩序"
            description_input.send_keys(feedback_text)
            time.sleep(1)
            
            # 填写联系方式
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.feedback-email"))
            )
            email_input.clear()
            email_input.send_keys("huiyun@fuyuncn.com")
            time.sleep(1)
            
            # 选择反馈类型
            feedback_type = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '网页打不开、提示内容已删除和无法找到该网页')]"))
            )
            feedback_type.click()
            time.sleep(1)
            
            # 点击提交按钮
            submit_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.feedback-submit"))
            )
            submit_btn.click()
            time.sleep(1)
            
            # 等待验证码完成
            logger.info("请完成人工验证...")
            try:
                self.wait.until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".verify-box"))
                )
                logger.info("验证完成")
                return True
            except TimeoutException:
                logger.warning("等待验证码超时，请手动处理")
                return False
            
        except Exception as e:
            logger.error(f"提交反馈失败: {str(e)}")
            return False

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_link = self.wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "下一页>"))
            )
            
            if not next_link:
                return False
            
            # 点击下一页
            next_link.click()
            time.sleep(1)  # 等待页面加载
            
            return True
            
        except (NoSuchElementException, TimeoutException):
            return False

    def process_search_results(self, results: List[Dict[str, Any]]) -> None:
        """处理搜索结果"""
        for index, result in enumerate(results, 1):
            try:
                logger.info(f"检查第 {index} 条结果: {result['title']}")
                logger.info(f"URL: {result['url']}")
                
                # 检查链接是否过期
                is_expired = self.check_expired(result['url'])
                logger.info(f"检查结果: {'已过期' if is_expired else '正常'}")
                
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