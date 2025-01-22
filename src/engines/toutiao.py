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
                "div.cs-view.pad-bottom-3.cs-view-block.cs-text.align-items-center"
            )
            
            print(f"找到 {len(result_items)} 个结果项")
            
            for index, item in enumerate(result_items):
                try:
                    print(f"\n处理第 {index + 1} 个结果项:")
                    print(f"结果项HTML: {item.get_attribute('outerHTML')}")
                    
                    # 获取标题和链接 - 尝试多个可能的选择器
                    title_element = None
                    for selector in ["a", "a.cs-title", ".cs-title a", "div.cs-title a"]:
                        try:
                            title_element = item.find_element(By.CSS_SELECTOR, selector)
                            print(f"使用选择器 '{selector}' 成功找到标题元素")
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
                        parent = item.find_element(By.XPATH, "./..")
                        print(f"父元素HTML: {parent.get_attribute('outerHTML')}")
                        
                        feedback_element = parent.find_element(
                            By.CSS_SELECTOR, 
                            "div.cs-view.cs-view-block.cs-source-extra"
                        )
                        print("成功找到反馈按钮")
                    except NoSuchElementException:
                        print("在父元素中未找到反馈按钮，尝试其他方法")
                        # 尝试查找相邻元素
                        feedback_element = item.find_element(
                            By.XPATH,
                            "following-sibling::div[contains(@class, 'cs-source-extra')]"
                        )
                    
                    result = {
                        'title': title_element.text.strip(),
                        'url': title_element.get_attribute('href'),
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
            # 确保在原始窗口
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
            
            # 滚动到元素可见
            feedback_element = result['feedback_element']
            self.driver.execute_script("arguments[0].scrollIntoView(true);", feedback_element)
            time.sleep(1)
            
            # 鼠标悬停在反馈按钮上
            actions = ActionChains(self.driver)
            actions.move_to_element(feedback_element).perform()
            
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
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-dialog"))
            )
            
            # 选择举报类型
            report_types = report_dialog.find_elements(By.CSS_SELECTOR, "div.report-type-item")
            for type_item in report_types:
                if "页面无法访问" in type_item.text:
                    type_item.click()
                    print("选择举报类型:", type_item.text)
                    break
            
            time.sleep(1)
            
            # 填写举报描述
            description_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-content textarea"))
            )
            description_input.clear()
            description_input.send_keys(self.feedback_config['description'])
            print("已填写举报描述")
            
            # 填写联系方式
            email_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.report-contact input"))
            )
            email_input.clear()
            email_input.send_keys(self.feedback_config['email'])
            print("已填写联系方式")
            
            # 提交举报
            submit_btn = report_dialog.find_element(By.CSS_SELECTOR, "button.report-submit")
            print("找到提交按钮")
            submit_btn.click()
            time.sleep(2)
            print("已点击提交按钮")
            
        except Exception as e:
            print(f"提交反馈失败: {str(e)}")
            # 保存页面截图以便调试
            try:
                screenshot_path = f"feedback_error_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                print(f"错误截图已保存到: {screenshot_path}")
                
                # 保存页面源码
                html_path = f"feedback_error_{int(time.time())}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"页面源码已保存到: {html_path}")
            except:
                pass

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".cs-pagination-next")
            
            if not next_buttons:
                return False
                
            next_btn = next_buttons[0]
            
            # 检查是否可点击
            if "disabled" in next_btn.get_attribute("class"):
                return False
                
            # 点击下一页
            next_btn.click()
            time.sleep(2)
            
            return True
            
        except Exception:
            return False 