import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        """初始化数据库连接"""
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建搜索结果表 (改名为 results)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    search_engine TEXT NOT NULL,
                    is_expired BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建进度记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    search_engine TEXT NOT NULL,
                    current_page INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(keyword, search_engine)
                )
            ''')
            
            conn.commit()

    def save_result(self, result: dict) -> bool:
        """保存搜索结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO results (
                        keyword, title, url, search_engine, is_expired
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    result['keyword'],
                    result['title'],
                    result['url'],
                    result['search_engine'],
                    result['is_expired']
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存搜索结果失败: {str(e)}")
            return False

    def get_progress(self, keyword: str, search_engine: str) -> int:
        """获取搜索进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT current_page FROM progress 
                    WHERE keyword = ? AND search_engine = ?
                ''', (keyword, search_engine))
                result = cursor.fetchone()
                return result[0] if result else 1
        except Exception as e:
            logger.error(f"获取进度失败: {str(e)}")
            return 1

    def save_progress(self, keyword: str, search_engine: str, current_page: int) -> bool:
        """保存搜索进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO progress (keyword, search_engine, current_page)
                    VALUES (?, ?, ?)
                    ON CONFLICT(keyword, search_engine) 
                    DO UPDATE SET current_page = ?
                ''', (keyword, search_engine, current_page, current_page))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存进度失败: {str(e)}")
            return False 