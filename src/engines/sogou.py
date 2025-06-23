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
            time.sleep(3)
            
            # 选择"删除快照"选项
            try:
                # 使用准确的选择器
                delete_option = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.delradio[name='kuaizhaotype'][value='1']"))
                )
                self.driver.execute_script("arguments[0].click();", delete_option)
                logger.info("成功选择删除快照选项")
            except Exception as e:
                logger.error(f"选择删除快照选项失败: {str(e)}")
                return False
            
            # 确保选项被选中
            time.sleep(1)
            
            # 填写快照地址
            try:
                # 使用准确的选择器
                url_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.vr-input-box[name='KuaizhaoDelete[webAdr][]']"))
                )
                
                # 使用 JavaScript 清除和设置值
                self.driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].style.color = '#000';
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """, url_input, result['url'])
                
                logger.info("成功填写快照地址")
                
                # 等待验证通过
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"填写快照地址失败: {str(e)}")
                return False
            
            # 填写原因描述
            try:
                description = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "textarea.des-area[name='KuaizhaoDelete[reason]']"))
                )
                
                # 使用 JavaScript 设置值并触发事件
                self.driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].style.color = '#000';
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """, description, self.feedback_config['description'])
                
                logger.info("成功填写原因描述")
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"填写原因描述失败: {str(e)}")
                return False
            
            # 选择申请人类型为"单位/公司"
            try:
                company_radio = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.delradio[name='apptypeForm1'][value='2']"))
                )
                self.driver.execute_script("arguments[0].click();", company_radio)
                logger.info("成功选择申请人类型：单位/公司")
                time.sleep(1)
            except Exception as e:
                logger.error(f"选择申请人类型失败: {str(e)}")
                return False

            # 上传有效资料
            try:
                logger.info("开始上传资质文件")
                
                for index, image_path in enumerate(self.engine_config['qualification_images']):
                    # 获取绝对路径
                    full_path = os.path.abspath(os.path.join(self.config['qualification_dir'], image_path))
                    if not os.path.exists(full_path):
                        logger.error(f"文件不存在: {full_path}")
                        continue
                    
                    logger.info(f"准备上传第 {index + 1} 个文件: {image_path}")
                    
                    # 点击添加附件按钮，生成新的文件选择区域
                    try:
                        add_file_button = self.wait.until(
                            EC.element_to_be_clickable((By.ID, "imgAddForm1"))
                        )
                        
                        # 使用JavaScript点击按钮，触发goAdd函数
                        self.driver.execute_script("goAdd('imgForm1','Form1');")
                        time.sleep(3)  # 等待新的文件选择区域生成
                        
                        logger.info(f"成功点击添加附件按钮，生成第 {index + 1} 个文件选择区域")
                        
                    except Exception as e:
                        logger.error(f"点击添加附件按钮失败: {str(e)}")
                        # 如果找不到主按钮，尝试直接点击链接
                        try:
                            add_link = self.wait.until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '添加附件')]"))
                            )
                            self.driver.execute_script("arguments[0].click();", add_link)
                            time.sleep(3)
                            logger.info("通过链接成功点击添加附件")
                        except Exception as e2:
                            logger.error(f"通过链接点击添加附件也失败: {str(e2)}")
                            continue
                    
                    # 查找新生成的文件输入框并上传文件
                    try:
                        # 查找表单区域内所有的文件输入框
                        form_area = self.driver.find_element(By.ID, "imgForm1")
                        file_inputs = form_area.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        
                        if len(file_inputs) > index:
                            # 使用对应索引的文件输入框
                            file_input = file_inputs[index]
                            logger.info(f"找到第 {index + 1} 个文件输入框")
                        else:
                            # 如果索引超出范围，使用最后一个文件输入框
                            file_input = file_inputs[-1] if file_inputs else None
                            logger.info(f"使用最后一个文件输入框 (共 {len(file_inputs)} 个)")
                        
                        if not file_input:
                            logger.error("无法找到合适的文件输入框")
                            continue
                        
                        # 确保文件输入框可见和可用
                        self.driver.execute_script("""
                            arguments[0].style.display = 'block';
                            arguments[0].style.visibility = 'visible';
                            arguments[0].style.opacity = '1';
                            arguments[0].style.position = 'static';
                            arguments[0].style.width = 'auto';
                            arguments[0].style.height = 'auto';
                            arguments[0].removeAttribute('hidden');
                        """, file_input)
                        
                        time.sleep(1)
                        
                        # 上传文件
                        file_input.send_keys(full_path)
                        logger.info(f"成功上传文件到第 {index + 1} 个位置: {image_path}")
                        
                        # 等待文件上传完成
                        time.sleep(1)
                        
                        # 检查该文件是否上传成功
                        try:
                            # 等待一小段时间让上传处理完成
                            time.sleep(1)
                            
                            # 重新查找文件输入框来检查文件名
                            updated_file_inputs = form_area.find_elements(By.CSS_SELECTOR, "input[type='file']")
                            if len(updated_file_inputs) > index:
                                current_file_input = updated_file_inputs[index]
                                file_value = current_file_input.get_attribute('value')
                                if file_value and image_path in file_value:
                                    logger.info(f"文件 {image_path} 上传成功，显示值: {file_value}")
                                else:
                                    logger.warning(f"文件 {image_path} 上传状态不确定")
                            
                        except Exception as e:
                            logger.warning(f"检查文件 {image_path} 上传状态时出错: {str(e)}")
                        
                        # 为下一个文件做准备
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"上传文件 {image_path} 失败: {str(e)}")
                        continue
                
                logger.info("所有资质文件上传处理完成")
                
            except Exception as e:
                logger.error(f"上传文件过程失败: {str(e)}")
                # 不返回 False，继续执行后续步骤
                logger.info("尽管文件上传可能失败，但继续执行后续步骤")

            # 填写联系方式（邮箱）
            try:
                # 确保联系方式类型选择为"邮箱"（默认应该已经是邮箱）
                contact_type_span = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "webContactWayDefaultForm1"))
                )
                
                # 检查当前选择的联系方式类型
                current_contact_type = contact_type_span.text.strip()
                logger.info(f"当前联系方式类型: {current_contact_type}")
                
                # 如果不是邮箱，点击选择邮箱
                if current_contact_type != "邮箱":
                    # 点击下拉框
                    self.driver.execute_script("showSelect('Form1');")
                    time.sleep(1)
                    
                    # 选择邮箱选项
                    email_option = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#webContactWaySelectForm1 a.webContactWaySelectValue"))
                    )
                    self.driver.execute_script("hideSelect(arguments[0],'Form1');", email_option)
                    time.sleep(1)
                    logger.info("成功选择邮箱联系方式")
                
                # 填写邮箱地址
                email_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "contactForm1"))
                )
                
                # 使用JavaScript清除并设置邮箱值
                self.driver.execute_script("""
                    arguments[0].value = '';
                    arguments[0].focus();
                """, email_input)
                time.sleep(0.5)
                
                email_input.send_keys(self.feedback_config['email'])
                
                # 触发blur事件以验证邮箱格式
                self.driver.execute_script("""
                    arguments[0].blur();
                    arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """, email_input)
                
                time.sleep(1)
                
                # 检查是否显示正确图标
                try:
                    ok_icon = self.driver.find_element(By.ID, "webContactWayOkForm1")
                    if ok_icon.is_displayed():
                        logger.info("邮箱格式验证成功")
                    else:
                        logger.warning("邮箱格式验证图标未显示")
                except:
                    logger.warning("未找到邮箱验证成功图标")
                
                # 检查是否显示错误提示
                try:
                    error_tip = self.driver.find_element(By.ID, "webContactWayErrorForm1")
                    if error_tip.is_displayed():
                        logger.error(f"邮箱填写出现错误提示: {error_tip.text}")
                    else:
                        logger.info("邮箱填写无错误提示")
                except:
                    logger.info("未找到错误提示元素")
                
                logger.info(f"成功填写联系方式邮箱: {self.feedback_config['email']}")
                
            except Exception as e:
                logger.error(f"填写联系方式失败: {str(e)}")
                return False
            
            # 等待用户完成验证码验证
            # try:
            #     # 创建一个新的 WebDriverWait 实例，设置超时时间为 10s
            #     long_wait = WebDriverWait(self.driver, 10)
            #     long_wait.until(
            #         lambda driver: driver.find_element(
            #             By.CSS_SELECTOR, 
            #             "div.success-message"
            #         ).is_displayed()
            #     )
            # except TimeoutException:
            #     logger.error("等待验证码验证超时(10s)")
            #     return False
            
            # 提交表单
            submit_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '提交')]"))
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