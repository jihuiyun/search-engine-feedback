from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base import SearchEngine
import time
from selenium.webdriver.remote.webdriver import WebDriver
import logging
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class ToutiaoEngine(SearchEngine):
    def __init__(self, config_path: str, browser_manager):
        super().__init__(config_path, browser_manager)
        self.engine_config = self.config['engines']['toutiao']
        self.feedback_config = self.config['feedback']

    def search(self, keyword: str) -> None:
        """执行头条搜索"""
        try:
            if not self.ensure_browser():
                logger.warning("浏览器已重新初始化")
            
            search_url = self.engine_config['url'].format(keyword=keyword)
            self.driver.get(search_url)
            time.sleep(3)
        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")
            return None

    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果列表"""
        results = []
        try:
            # 等待搜索结果加载
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".result-content"))
            )
            time.sleep(2)  # 额外等待确保页面完全加载
            
            # 获取所有搜索结果项的容器
            result_items = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.cs-view.pad-bottom-3.cs-view-block.cs-header.align-items-center"
            )
            
            print(f"找到 {len(result_items)} 个结果项")
            
            for index, item in enumerate(result_items):
                try:
                    print(f"\n处理第 {index + 1} 个结果项:")

                    # 获取标题和链接 - 尝试多个可能的选择器
                    title_element = None
                    for selector in ["a", "a.cs-title", ".cs-title a", "div.cs-title a"]:
                        try:
                            title_element = item.find_element(By.CSS_SELECTOR, selector)
                            break
                        except NoSuchElementException:
                            print(f"选择器 '{selector}' 未找到标题元素")
                            continue
                    
                    if not title_element:
                        print("未能找到标题元素，跳过此结果项")
                        continue
                    
                    # 获取反馈按钮
                    try:
                         # 先尝试在当前元素的父元素中查找
                        parent = item.find_element(By.XPATH, "./../../../../..")
                        feedback_element = parent.find_element(
                            By.CSS_SELECTOR, 
                            "div.cs-view.cs-view-block.cs-source-extra"
                        )
                        print("成功找到反馈按钮")
                    except NoSuchElementException:
                        print("未找到反馈按钮")
                        continue

                    # 获取真实的 URL
                    raw_url = title_element.get_attribute('href')
                    real_url = raw_url.split('url=')[-1] if 'url=' in raw_url else raw_url
                    real_url = real_url.split('&')[0]  # 取出第一个参数，确保只得到 URL
                    real_url = unquote(real_url)  # 进行 URL 解码
                    
                    result = {
                        'title': title_element.text.strip(),
                        'url': real_url,
                        'element': item,
                        'feedback_element': feedback_element
                    }
                    print(f"成功解析结果: {result['title']}")
                    results.append(result)
                    
                except NoSuchElementException as e:
                    print(f"解析搜索结果项时出错: {str(e)}")
                    continue
                except Exception as e:
                    print(f"处理结果项时发生未知错误: {str(e)}")
                    continue
                
            print(f"\n总共成功解析 {len(results)} 个结果")
            
        except TimeoutException:
            print("获取搜索结果超时")
        except Exception as e:
            print(f"获取搜索结果出错: {str(e)}")
            
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

    def submit_feedback(self, result: Dict[str, Any]) -> None:
        """提交反馈"""
        try:
            # 确保在原始窗口
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
            
            # 滚动到元素可见
            element = result['element']
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(1)
            
            # 鼠标悬停在反馈按钮上
            actions = ActionChains(self.driver)
            actions.move_to_element(result['feedback_element']).perform()
            
            # 等待悬停菜单出现并确认其中包含"举报反馈"选项
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '举报反馈')]"))
            )
            time.sleep(1)  # 额外等待确保菜单完全显示
            
            # 使用精确的CSS选择器查找举报反馈按钮
            report_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.cs-trigger-popup.cs-trigger-popup-open>div"))
            )
            report_btn.click()
            time.sleep(2)
            
            # 等待举报对话框出现
            report_dialog = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cs-feedback-wrap.cs-feedback-wrap-open"))
            )
            
            # 选择举报类型
            report_types = report_dialog.find_elements(By.CSS_SELECTOR, "div.cs-feedback-wrap.cs-feedback-wrap-open div.report-type-item")
            match_strings = ["页面打不开，无法找到网页", "视频内容陈旧", "内容陈旧"] 
            
            for type_item in report_types:
                if any(match_string in type_item.text for match_string in match_strings):
                    type_item.click()
                    print("选择举报类型:", type_item.text)
                    break
            
            time.sleep(1)
            
            # 填写举报描述
            description_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cs-feedback-wrap.cs-feedback-wrap-open textarea.cs-feedback-detail"))
            )
            description_input.clear()
            description_input.send_keys(self.feedback_config['description'])
            print("已填写举报描述")
            
            # 填写联系方式
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cs-feedback-wrap.cs-feedback-wrap-open input.cs-feedback-contact"))
            )
            email_input.clear()
            email_input.send_keys(self.feedback_config['email'])
            print("已填写联系方式")
            
            # 提交举报
            submit_btn = report_dialog.find_element(By.XPATH, "//div[contains(@class, 'cs-view') and contains(@class, 'cursor-pointer')]//span[text()='确定']")
            print("找到提交按钮")
            submit_btn.click()
            time.sleep(2)
            print("已点击提交按钮")
            
        except Exception as e:
            print(f"提交反馈失败: {str(e)}")

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
            
        except Exception:
            return False 

    def process_search_results(self, results: List[Dict[str, Any]]) -> None:
        """串行处理搜索结果"""
        for index, result in enumerate(results, 1):
            try:
                # 确保浏览器会话有效
                if not self.ensure_browser():
                    logger.warning("浏览器已重新初始化，重新加载页面")
                    self.driver.get(self.driver.current_url)
                    time.sleep(3)
                
                logger.info(f"检查第 {index} 条结果: {result['title']}")
                logger.info(f"URL: {result['url']}")
                
                # 检查链接是否过期
                is_expired = self.check_expired(result['url'])
                logger.info(f"检查结果: {'已过期' if is_expired else '正常'}")
                
                if is_expired:
                    try:
                        # 再次确保浏览器会话有效
                        if not self.ensure_browser():
                            logger.warning("浏览器已重新初始化，重新加载页面")
                            self.driver.get(self.driver.current_url)
                            time.sleep(3)
                        
                        # 尝试重新获取元素（因为页面可能已经刷新）
                        result_items = self.driver.find_elements(
                            By.CSS_SELECTOR, 
                            "div.cs-view.pad-bottom-3.cs-view-block.cs-text.align-items-center"
                        )
                        for item in result_items:
                            title_element = item.find_element(By.CSS_SELECTOR, "a")
                            if title_element.get_attribute('href') == result['url']:
                                result['element'] = item
                                break
                        
                        # 添加红色边框标记
                        self.driver.execute_script("""
                            var element = arguments[0];
                            element.style.border = '5px solid red';
                            element.style.boxShadow = '0 0 10px red';
                            element.style.position = 'relative';
                            element.style.zIndex = '1000';
                            element.scrollIntoView({behavior: 'smooth', block: 'center'});
                        """, result['element'])
                        
                        logger.info(f"发现过期链接，等待用户操作反馈: {result['url']}")
                        
                        # 无限等待用户触发反馈对话框
                        while True:
                            try:
                                # 检查反馈对话框是否出现
                                dialog_present = self.wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-dialog"))
                                )
                                if dialog_present:
                                    logger.info("检测到反馈对话框，开始自动填充")
                                    break
                            except TimeoutException:
                                logger.info("等待用户点击反馈按钮...")
                                time.sleep(5)  # 每5秒检查一次
                                # 确保浏览器会话仍然有效
                                if not self.ensure_browser():
                                    raise Exception("浏览器会话已断开")
                        
                        # 选择举报类型
                        report_types = self.driver.find_elements(By.CSS_SELECTOR, "div.report-type-item")
                        for type_item in report_types:
                            if "页面无法访问" in type_item.text:
                                type_item.click()
                                logger.info("已选择举报类型: 页面无法访问")
                                break
                        time.sleep(1)
                        
                        # 填写举报描述
                        description_input = self.wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-content textarea"))
                        )
                        description_input.clear()
                        description_input.send_keys(self.feedback_config['description'])
                        logger.info("已填写举报描述")
                        
                        # 填写联系方式
                        email_input = self.wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-contact input"))
                        )
                        email_input.clear()
                        email_input.send_keys(self.feedback_config['email'])
                        logger.info("已填写联系方式")
                        
                        # 点击确定按钮
                        submit_btn = self.wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.report-submit"))
                        )
                        submit_btn.click()
                        logger.info("已点击确定按钮")
                        
                        # 等待反馈对话框消失
                        self.wait.until_not(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-dialog"))
                        )
                        logger.info("反馈提交完成")
                        
                    except Exception as e:
                        logger.error(f"处理反馈时出错: {str(e)}")
                        raise  # 重新抛出异常，让外层处理
                    finally:
                        try:
                            # 移除红色边框标记
                            if self.ensure_browser():
                                self.driver.execute_script("""
                                    var element = arguments[0];
                                    element.style.border = '';
                                    element.style.boxShadow = '';
                                    element.style.position = '';
                                    element.style.zIndex = '';
                                """, result['element'])
                        except:
                            pass
                    
                    time.sleep(2)  # 等待一段时间再处理下一条结果
                
            except Exception as e:
                logger.error(f"处理搜索结果时出错: {str(e)}")
                # 保存错误截图和页面源码
                try:
                    if self.ensure_browser():
                        timestamp = int(time.time())
                        error_prefix = f"toutiao_process_error_{timestamp}"
                        
                        # 保存截图
                        screenshot_path = f"{error_prefix}.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.error(f"错误截图已保存到: {screenshot_path}")
                        
                        # 保存页面源码
                        html_path = f"{error_prefix}.html"
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(self.driver.page_source)
                        logger.error(f"页面源码已保存到: {html_path}")
                except:
                    pass
                return  # 出错时停止处理后续结果 

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
                    self.config['selectors']['toutiao']['feedback_success']
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
            logger.warning("等待头条反馈完成超时") 

    def get_current_page(self) -> int:
        """获取头条搜索当前页码"""
        try:
            # 查找当前页码元素
            current = self.driver.find_element(
                By.CSS_SELECTOR, 
                "button.cs-pagination-item.active"
            )
            return int(current.text)
        except (NoSuchElementException, ValueError):
            return 1 

    def get_domain(self) -> str:
        return "toutiao.com"

    def check_login(self) -> bool:
        try:
            # 检查是否有登录按钮
            login_btn = self.driver.find_elements(By.CLASS_NAME, "login-button")
            if login_btn and login_btn[0].is_displayed():
                return False
                
            # 检查是否有用户头像
            avatar = self.driver.find_elements(By.CLASS_NAME, "user-avatar")
            return bool(avatar and avatar[0].is_displayed())
        except Exception:
            return False 