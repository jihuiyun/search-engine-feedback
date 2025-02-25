import time
from rotate_image_classifier import *

class CalcAngle: 
    def __init__(self) -> None:
        pass

    def get_img_file(self):
        """
        获取旋转验证码图片
        """
        img_url = self.style_content['data']['captchalist'][0]['source']['back']['path']
        print('获取到的图片链接', img_url)
        response = requests.get(img_url, headers=self.base_headers)
        with open('img_file/demo_aqc.png', 'wb') as f:
            f.write(response.content)
        
        time.sleep(1)

        predicted_angle= get_result('img_file/demo_aqc.png')
        # results, avg_diff = get_result('img_file')
        # predicted_angle = results[0]['Infer']
        return predicted_angle