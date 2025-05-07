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
import sqlite3
from selenium.webdriver.common.action_chains import ActionChains
# 导入百度旋转验证码求解器
from src.verification.baidu.baidu_rotate_captcha_solver import solve_rotation_captcha

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
        self.db_conn = sqlite3.connect(self.config['database']['path'])

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
            search_url = f"{self.engine_config['url']}s?wd={keyword}"
            logger.info(f"开始搜索: {keyword}")
            logger.info(f"访问URL: {search_url}")
            
            self.driver.get(search_url)
            # time.sleep(2)
            
            # 检查登录状态
            while True:  # 添加循环来处理所有可能的状态
                # 检查是否需要验证码
                if self.check_verification():
                    logger.info("检测到需要验证码，等待处理...")
                    if not self.wait_for_verification():
                        logger.error("验证码处理失败，跳过当前搜索")
                        return None
                    time.sleep(2)  # 等待页面刷新
                    continue  # 验证码处理完后重新检查状态
                
                # 检查登录状态
                if not self.check_login():
                    # 第一次尝试使用 cookies 登录
                    if not hasattr(self, '_tried_cookies'):
                        logger.info("尝试使用 cookies 登录")
                        self._tried_cookies = True
                        if self.browser_manager.load_cookies('baidu.com'):
                            # 刷新页面使 cookies 生效
                            self.driver.refresh()
                            time.sleep(2)
                            continue  # 重新检查状态
                    
                    # cookies 登录失败或没有 cookies，等待手动登录
                    logger.warning("等待用户手动登录...")
                    login_timeout = 60  # 设置登录超时时间为60秒
                    login_start_time = time.time()
                    
                    while not self.check_login():
                        if time.time() - login_start_time > login_timeout:
                            logger.error("登录超时，跳过当前搜索")
                            return None
                        time.sleep(2)
                        if not self.ensure_browser():
                            logger.error("浏览器连接断开，跳过当前搜索")
                            return None
                        
                        # 检查是否需要验证码
                        if self.check_verification():
                            if not self.wait_for_verification():
                                logger.error("验证码处理失败，跳过当前搜索")
                                return None
                            time.sleep(2)  # 等待页面刷新
                            break  # 验证码处理完后跳出内层循环，重新检查状态
                    
                    continue  # 重新检查状态
                
                # 登录成功，保存 cookies
                logger.info("登录成功，保存 cookies")
                print("登录成功，保存 cookies")
                self.browser_manager.save_cookies('baidu.com')
                break  # 所有状态都正常，退出循环
            
            logger.info("登录状态正常，继续搜索流程")
            
        except Exception as e:
            logger.error(f"搜索出错: {str(e)}")
            return None

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
                        # time.sleep(2)
                        continue
                except NoSuchElementException:
                    # 检查是否已登录成功（查找用户头像）
                    try:
                        user_avatar = self.driver.find_element(By.CLASS_NAME, "user-name")
                        if user_avatar.is_displayed():
                            logger.info("登录成功")
                            print("登录成功")
                            return True
                    except NoSuchElementException:
                        logger.info("等待登录完成...")
                        # time.sleep(2)
                        continue
                
        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            return False

    def get_search_results(self) -> List[Dict[str, Any]]:
        """获取搜索结果列表"""
        results = []
        try:
            # 等待搜索结果加载
            logger.info("等待搜索结果加载...")
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, "content_left")))
                logger.info("搜索结果加载完成")
            except TimeoutException:
                logger.error("搜索结果加载超时")
                return results
            
            # 获取所有搜索结果项
            result_items = self.driver.find_elements(By.CSS_SELECTOR, "div.result.c-container, div.result-op.c-container")
            logger.info(f"找到 {len(result_items)} 条搜索结果")
            
            for item in result_items:
                try:
                    # 获取标题元素和文本
                    # 尝试不同的标题选择器
                    title_element = None
                    for selector in ["h3.t a", "h3.c-title a", "h3 a"]:
                        try:
                            title_element = item.find_element(By.CSS_SELECTOR, selector)
                            break
                        except NoSuchElementException:
                            continue
                    
                    if not title_element:
                        logger.debug("未找到标题元素，跳过当前结果")
                        continue

                    # 获取标题
                    title = title_element.text.strip()
                    logger.debug(f"处理搜索结果: {title}")
                    
                    # 检查标题是否重复
                    if any(r['title'] == title for r in results):
                        logger.debug(f"跳过重复标题: {title}")
                        continue

                    # 从父级 div 的 mu 属性获取真实 URL
                    url = item.get_attribute('mu') or title_element.get_attribute('href')
                    if not url:
                        logger.debug("未找到URL，跳过当前结果")
                        continue
                    
                    result = {
                        'title': title,
                        'url': url,
                        'element': item
                    }
                    results.append(result)
                    logger.debug(f"成功添加搜索结果: {title}")
                    print(f"成功添加搜索结果: {title}")
                except Exception as e:
                    logger.error(f"处理搜索结果项时出错: {str(e)}")
                    continue
                
            logger.info(f"共处理 {len(results)} 条有效搜索结果")
            return results
            
        except Exception as e:
            logger.error(f"获取搜索结果失败: {str(e)}")
            return []

    def check_expired(self, url: str) -> bool:
        """检查链接是否过期"""
        if not self.ensure_browser():
            logger.error("浏览器连接断开，无法检查链接")
            return False
            
        current_window = self.driver.current_window_handle
        logger.info(f"开始检查链接: {url}")
        
        try:
            # 新标签页打开链接
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            # time.sleep(1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载
            time.sleep(1)
            
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
            
        except Exception as e:
            logger.error(f"检查链接时出错: {str(e)}")
            return False
        finally:
            try:
                self.driver.close()
                self.driver.switch_to.window(current_window)
                time.sleep(1)
            except Exception as e:
                logger.error(f"关闭标签页时出错: {str(e)}")
                # 如果关闭失败，尝试重新初始化浏览器
                self.ensure_browser()

    def submit_feedback(self, result: Dict[str, Any]) -> bool:
        """提交反馈"""
        try:
            # 确保在主窗口
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                time.sleep(1)
            
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # 查找并点击页面底部的反馈按钮
            feedback_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.feedback"))
            )
            feedback_btn.click()
            time.sleep(1)

            # 等待反馈弹窗加载
            try:
                # 找到反馈元素点击定位块
                element_block = result['element'].find_element(By.CSS_SELECTOR, "div.fb-list-container")  # 替换为实际的选择器

                self.driver.execute_script("arguments[0].scrollIntoView();", element_block)
                self.driver.execute_script("arguments[0].click();", element_block);

                # 等待弹窗完全加载
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#fb_baidu_list_dialog"))
                )

                # 填写反馈描述
                description = (
                    "网页打不开，提示内容已删除或找不到该网页，请删除快照，且快照包含91y关键词信息为不实内容，"
                    "误导91y游戏用户，已严重影响到浮云公司的商誉和正常的经营秩序"
                )
                
                # 模拟真实的键盘输入
                self.driver.execute_script("""
                    function triggerEvent(element, eventType) {
                        const event = new Event(eventType, { bubbles: true });
                        element.dispatchEvent(event);
                    }
                    
                    function simulateTyping(element, text) {
                        element.focus();
                        triggerEvent(element, 'focus');
                        element.value = text;
                        triggerEvent(element, 'input');
                        triggerEvent(element, 'change');
                        triggerEvent(element, 'blur');
                    }
                    
                    const textarea = document.querySelector('#fb_baidu_list_dialog div.fb-textarea.fb-content-block>textarea');
                    const emailInput = document.querySelector('#fb_baidu_list_dialog input.fb-email');
                    
                    if (textarea) {
                        simulateTyping(textarea, arguments[0]);
                    }
                    
                    if (emailInput) {
                        simulateTyping(emailInput, arguments[1]);
                    }
                """, description, "huiyun@fuyuncn.com")
                
                # 点击提交按钮
                submit_btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#fb_list_post_save"))
                )
                submit_btn.click()
                time.sleep(1)
                # 等待用户完成安全验证
                logger.info("准备完成安全验证...")
                try:
                    if self.check_verification():
                        if not self.wait_for_verification():
                            logger.error("验证码处理失败")
                            return False
                        
                    # 创建一个更长超时时间的 wait 对象
                    long_wait = WebDriverWait(self.driver, 1200)  
                    # 等待验证弹窗消失
                    long_wait.until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "#fb_baidu_list_dialog div.fb-vertify"))
                    )
                    logger.info("安全验证完成")
                except TimeoutException:
                    logger.error("等待安全验证超时（30秒）")
                    return False
                
                logger.info("反馈提交成功")
                return True
                
            except Exception as e:
                logger.error(f"反馈表单处理失败: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"提交反馈失败: {str(e)}")
            return False

    def next_page(self) -> bool:
        """跳转到下一页"""
        try:
            # 查找下一页按钮
            next_link = self.wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "下一页 >"))
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
                    self.config['selectors']['baidu']['feedback_success']
                ))
            )
            # 等待反馈成功提示消失
            self.wait.until(
                EC.invisibility_of_element(success_element)
            )
        except TimeoutException:
            logger.warning("等待百度反馈完成超时")

    def get_current_page(self) -> int:
        """获取百度搜索当前页码"""
        try:
            # 查找页码指示器
            page_div = self.driver.find_element(By.CSS_SELECTOR, "div#page")
            current = page_div.find_element(By.CSS_SELECTOR, "strong.pc")
            return int(current.text)
        except (NoSuchElementException, ValueError):
            return 1  # 默认返回第1页 

    def get_domain(self) -> str:
        return "baidu.com"

    def check_login(self) -> bool:
        """检查是否已登录"""
        try:
            # 检查是否存在账号登录弹窗
            account_login_dialog = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'div.passport-login-pop-dialog'
            )
            if account_login_dialog and account_login_dialog[0].is_displayed():
                logger.info("检测到账号登录弹窗")
                return False
            
            # 检查登录按钮
            login_btn = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'a[name="tj_login"].lb[href*="passport.baidu.com"]'
            )
            if login_btn and login_btn[0].is_displayed():
                logger.info("检测到登录按钮")
                return False
            
            logger.info("检测到已登录状态")
            return True
            
        except Exception as e:
            logger.error(f"检查登录状态出错: {str(e)}")
            return False

    def check_verification(self) -> bool:
        """检查是否需要验证码"""
        try:
            # 直接查找包含"请完成下方验证后继续操作"文本的元素
            verification_elements = self.driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), '请完成下方验证后继续操作')]"
            )
            
            if verification_elements and len(verification_elements) > 0:
                logger.info("检测到需要验证码：找到'请完成下方验证后继续操作'文本")
                return True
            
            # 保留原有的检测方法作为备选
            verify_dialog = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'div.passMod_dialog-container'
            )
            if verify_dialog and verify_dialog[0].is_displayed():
                logger.info("通过备选方法检测到需要验证码")
                return True
                
            return False
        except Exception as e:
            logger.error(f"检查验证码状态出错: {str(e)}")
            return False

    def wait_for_verification(self) -> bool:
        """等待完成验证码，优先使用自动处理，失败则等待用户手动完成"""
        try:
            logger.info("检测到验证码，尝试自动处理...")
            
            # 检查是否是旋转验证码
            spin_img = self.driver.find_elements(By.CSS_SELECTOR, "img.vcode-spin-img")
            if spin_img and len(spin_img) > 0:
                logger.info("检测到旋转验证码，启动自动求解...")
                result = solve_rotation_captcha(self.driver)#旋转模型
                if result:
                    logger.info("旋转验证码自动处理成功")
                    return True
                else:
                    logger.warning("旋转验证码自动处理失败，请手动完成验证...")
            else:
                logger.info("未检测到可自动处理的验证码类型，等待手动处理...")
            
            # 如果自动处理失败或不是已知的验证码类型，等待用户手动处理
            max_wait_time = 120  # 最长等待2分钟
            start_time = time.time()
            
            while self.check_verification():
                elapsed_time = time.time() - start_time
                if elapsed_time > max_wait_time:
                    logger.error(f"等待验证码完成超时（{max_wait_time}秒）")
                    return False
                    
                time.sleep(2)
                if not self.ensure_browser():
                    return False
                    
            logger.info("验证码已完成")
            return True
            
        except Exception as e:
            logger.error(f"等待验证码完成出错: {str(e)}")
            return False 