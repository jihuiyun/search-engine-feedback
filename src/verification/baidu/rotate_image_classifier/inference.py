# !/usr/bin/env python3
"""
验证训练模型。

Author: pankeyu
Date: 2022/05/19
"""
import os
import sys
import requests
import numpy as np
from io import BytesIO
import logging
import cv2
import pickle

import torch
import torch.nn as nn
from torchvision import models
import torch.nn.functional as F
from torch.serialization import add_safe_globals

# 添加日志记录
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(handler)

input_shape = (3, 224, 224)  # 修正为224x224，标准ResNet输入尺寸

class RotateNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = models.resnet50(pretrained=False)  # 不加载预训练权重
        self.model.fc = nn.Linear(2048, 360)

    def forward(self, x):
        """
        前向传播，使用resnet 50作为backbone，后面接一个线性层。

        Args:
            x (_type_): (batch, 3, 224, 224)

        Returns:
            _type_: 360维的一个tensor，表征属于每一个角度类别的概率
        """
        x = self.model(x)
        return x

# 添加类重定向，解决模块不匹配问题
class _RenameUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # 将__main__.RotateNet重定向到当前模块的RotateNet
        if module == "__main__" and name == "RotateNet":
            return RotateNet
        return super().find_class(module, name)

def custom_load(file_obj):
    """自定义模型加载函数，处理模块重定向"""
    return _RenameUnpickler(file_obj).load()

def preprocess_image(img_path, input_shape=(3, 224, 224)):
    """
    使用OpenCV对图像进行预处理，与原始项目保持一致
    """
    try:
        if img_path.startswith(('http://', 'https://')):
            # 下载在线图片
            logger.info(f"下载图片: {img_path}")
            response = requests.get(img_path, timeout=10)
            # 转换为OpenCV格式
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        else:
            # 加载本地图片
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error(f"无法加载图片: {img_path}")
            raise ValueError(f"无法加载图片: {img_path}")
            
        # OpenCV默认是BGR格式，转换为RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 裁剪为正方形（从中心裁剪）
        height, width = img.shape[:2]
        size = min(width, height)
        start_x = (width - size) // 2
        start_y = (height - size) // 2
        img = img[start_y:start_y + size, start_x:start_x + size]
        
        # 调整大小为224x224
        img = cv2.resize(img, (input_shape[1], input_shape[2]))
        
        # 转换为PyTorch所需的格式并归一化
        img = img.astype(np.float32) / 255.0
        
        # 应用ImageNet均值和标准差进行归一化
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        
        img = (img - mean) / std
        
        # 调整维度顺序（HWC->CHW）
        img = np.transpose(img, (2, 0, 1))
        img_tensor = torch.from_numpy(img).unsqueeze(0)  # 添加batch维度
        
        return img_tensor
    except Exception as e:
        logger.error(f"图像预处理失败: {e}")
        raise e

def getAngle(imgPath: str) -> int:
    """
    获取图片的旋转角度

    Args:
        imgPath (str): 图片路径或URL

    Returns:
        int: 预测的旋转角度 (0-359)
    """
    try:
        # 获取模型文件的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, 'models', 'model_13.pth')
        
        if not os.path.exists(model_path):
            logger.error(f"模型文件不存在: {model_path}")
            return 0
            
        # 创建一个新的模型实例
        model = RotateNet()
        
        # 加载模型权重
        try:
            # 将RotateNet类添加到安全的全局变量中
            add_safe_globals([RotateNet])
            
            # 尝试使用自定义加载函数处理模块重定向问题
            with open(model_path, 'rb') as f:
                checkpoint = custom_load(f)
            
            # 根据不同情况处理权重
            if isinstance(checkpoint, dict):
                if 'state_dict' in checkpoint:
                    model.load_state_dict(checkpoint['state_dict'])
                else:
                    model.load_state_dict(checkpoint)
            else:
                # 如果加载的是整个模型对象，提取其状态字典
                try:
                    model.load_state_dict(checkpoint.state_dict())
                except:
                    # 作为最后的尝试，直接使用加载的模型
                    model = checkpoint
            
            model.eval()
            logger.info("成功使用自定义加载函数加载模型权重")
        except Exception as e:
            # 如果自定义加载函数失败，尝试使用weights_only=False加载
            logger.warning(f"自定义加载函数失败，尝试其他方法: {e}")
            try:
                # 设置模块重定向
                sys.modules['__main__'] = sys.modules[__name__]
                
                # 使用weights_only=False加载
                checkpoint = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)
                
                if isinstance(checkpoint, dict):
                    if 'state_dict' in checkpoint:
                        model.load_state_dict(checkpoint['state_dict'])
                    else:
                        model.load_state_dict(checkpoint)
                else:
                    model = checkpoint
                
                model.eval()
                logger.info("使用模块重定向成功加载模型权重")
            except Exception as e2:
                logger.error(f"所有加载模型尝试均失败: {e2}")
                # 创建一个"干净"的模型
                model = RotateNet()
                model.eval()
                logger.warning("使用未训练的模型进行推理")

        # 预处理图像
        img_tensor = preprocess_image(imgPath, input_shape=input_shape)
        
        # 确保输入是float类型
        img_tensor = img_tensor.float()
        
        # 预测
        with torch.no_grad():
            logits = model(img_tensor)
            probs = F.softmax(logits, dim=-1)
            pred_angle = int(torch.argmax(probs, dim=1).item())
        
        logger.info(f"预测的旋转角度: {pred_angle}")
        return pred_angle

    except Exception as e:
        logger.error(f"预测图片旋转角度失败: {str(e)}")
        # 如果预测失败，返回默认角度
        return 0

# 测试代码，便于直接调试
if __name__ == '__main__':
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        # 尝试提取GitHub原始内容URL
        if "github.com" in image_path and "raw=true" not in image_path:
            # 如果是GitHub URL但不是raw格式，尝试替换为raw.githubusercontent.com
            image_path = image_path.replace("github.com", "raw.githubusercontent.com")
            image_path = image_path.replace("/blob/", "/")
        
        angle = getAngle(image_path)
        print(f"图片 {image_path} 的旋转角度为: {angle}°")
    else:
        print("请提供图片路径或URL作为参数")


