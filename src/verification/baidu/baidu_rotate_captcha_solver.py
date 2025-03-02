import time
from .rotate_image_classifier.inference import *
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def solve_rotation_captcha(driver, max_retries=30):
    """
    解决百度旋转验证码，如果失败会自动重试
    
    Args:
        driver: Selenium WebDriver 实例
        max_retries: 最大重试次数，默认20次
        
    Returns:
        bool: 验证是否成功
    """
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 等待验证码加载
            time.sleep(1)
            
            # 检查验证码是否还存在
            try:
                # 使用短超时等待验证码文本元素
                verification_text = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '拖动左侧滑块使图片为正')]"))
                )
                
                # 如果验证码文本不可见，说明已经验证成功
                if not verification_text.is_displayed():
                    print("验证成功，验证码已消失")
                    return True
                    
            except TimeoutException:
                # 如果找不到验证码文本，可能已经验证成功
                print("验证成功，验证码文本已消失")
                return True
            
            # 获取验证码图片的URL
            img_element = driver.find_element(By.CSS_SELECTOR, "img.vcode-spin-img")
            img_url = img_element.get_attribute("src")
            
            if not img_url:
                print(f"未找到验证码图片URL，重试次数: {retry_count + 1}/{max_retries}")
                retry_count += 1
                continue
                
            # 获取图片需要旋转的角度
            angle = getAngle(img_url)
       
            print(f"重试 {retry_count + 1}/{max_retries} - 获取到的旋转角度: {angle}")
            
            # 计算需要拖动的距离
            # 找到滑块和滑动区域元素
            slider = driver.find_element(By.CSS_SELECTOR, "div.vcode-spin-button")
            slider_container = driver.find_element(By.CSS_SELECTOR, "div.vcode-spin-bottom")
            
            # 获取滑块宽度和滑动区域的总宽度
            slider_width = slider.size['width']
            container_width = slider_container.size['width']
            
            # 可拖动的总长度 = 滑动区域宽度 - 滑块宽度
            total_drag_width = container_width - slider_width
            
            # 根据角度计算拖动距离：图片需要逆时针旋转，因此滑块需要向右移动
            # 计算需要拖动的距离：360度对应总拖动距离，角度对应的距离 = 角度/360 * 总距离
            drag_distance = (angle / 360) * total_drag_width
            
            # 创建一个动作链
            actions = ActionChains(driver)
            
            # 拖动滑块
            actions.click_and_hold(slider)
            actions.move_by_offset(drag_distance, 0)
            actions.release()
            actions.perform()
            
            # 等待验证结果
            time.sleep(2)
            
            # 检查验证是否成功（验证码文本消失）
            try:
                verification_text = driver.find_element(By.XPATH, "//*[contains(text(), '拖动左侧滑块使图片为正')]")
                if not verification_text.is_displayed():
                    print("验证成功，验证码已消失")
                    return True
            except NoSuchElementException:
                print("验证成功，验证码文本已消失")
                return True
                
            # 如果执行到这里，说明验证可能失败，检查是否有新的验证码图片
            old_img_url = img_url
            try:
                img_element = driver.find_element(By.CSS_SELECTOR, "img.vcode-spin-img")
                new_img_url = img_element.get_attribute("src")
                
                # 如果图片URL改变，说明需要重新验证
                if new_img_url != old_img_url:
                    print(f"验证失败，加载了新的验证码图片，将进行第 {retry_count + 2} 次尝试")
                else:
                    print(f"验证结果不明确，将进行第 {retry_count + 2} 次尝试")
            except:
                print(f"无法检查验证结果，将进行第 {retry_count + 2} 次尝试")
                
            # 增加重试计数
            retry_count += 1
            
        except NoSuchElementException as e:
            print(f"元素未找到: {e}")
            retry_count += 1
        except Exception as e:
            print(f"处理验证码时出错: {e}")
            retry_count += 1
            
    # 如果尝试次数达到上限，提示用户手动验证
    print(f"已达到最大重试次数 {max_retries}，请手动完成验证")
    return False
