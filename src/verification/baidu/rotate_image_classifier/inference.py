# !/usr/bin/env python3
"""
验证训练模型。

Author: pankeyu
Date: 2022/05/19
"""
import os
import requests
from PIL import Image
from io import BytesIO
import torchvision.transforms as transforms
import logging

import numpy as np
import torch
import torch.nn as nn
from torchvision import models
import torch.nn.functional as F

# Add after all imports
logger = logging.getLogger(__name__)

input_shape = (3, 244, 244)


class RotateNet(nn.Module):

    def __init__(self):
        super().__init__()
        self.model = models.resnet50(pretrained=True)
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
        
        # 初始化模型
        with torch.no_grad():
            # 直接加载完整模型
            model = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False).eval()

        # 处理图片路径/URL
        if imgPath.startswith(('http://', 'https://')):
            # 下载在线图片
            response = requests.get(imgPath, timeout=10)
            img = Image.open(BytesIO(response.content))
        else:
            # 加载本地图片
            img = Image.open(imgPath)

        # 图片预处理
        transform = transforms.Compose([
            transforms.Resize((244, 244)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # 转换图片格式
        img_tensor = transform(img).unsqueeze(0)  # 添加 batch 维度

        # 预测
        logits = model(img_tensor)
        probs = F.softmax(logits, dim=-1)
        pred_angle = int(torch.argmax(probs, dim=1).item())

        return pred_angle

    except Exception as e:
        logger.error(f"预测图片旋转角度失败: {str(e)}")
        raise e


