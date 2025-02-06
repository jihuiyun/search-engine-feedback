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
            
            # 检查 progress 表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='progress'
            """)
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                # 检查 is_done 列是否存在
                cursor.execute("PRAGMA table_info(progress)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'is_done' not in columns:
                    # 添加 is_done 列
                    cursor.execute("""
                        ALTER TABLE progress 
                        ADD COLUMN is_done BOOLEAN NOT NULL DEFAULT 0
                    """)
                    logger.info("数据库更新: 已向 progress 表添加 is_done 列")
            else:
                # 创建新的 progress 表
                cursor.execute('''
                    CREATE TABLE progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        search_engine TEXT NOT NULL,
                        current_page INTEGER NOT NULL DEFAULT 1,
                        is_done BOOLEAN NOT NULL DEFAULT 0,
                        UNIQUE(keyword, search_engine)
                    )
                ''')
                logger.info("数据库初始化: 已创建 progress 表")
            
            # 检查 results 表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='results'
            """)
            if not cursor.fetchone():
                # 创建搜索结果表
                cursor.execute('''
                    CREATE TABLE results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        search_engine TEXT NOT NULL,
                        is_expired BOOLEAN NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                logger.info("数据库初始化: 已创建 results 表")
            
            conn.commit()

    def check_url_exists(self, url: str) -> bool:
        """检查 URL 是否已经处理过"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM results 
                    WHERE url = ?
                ''', (url,))
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"数据库错误: 检查 URL 是否存在失败 - {str(e)}")
            return False

    def save_result(self, result: dict) -> bool:
        """保存搜索结果，即使 URL 已存在也保存"""
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
                logger.debug(f"已保存搜索结果: {result['title'][:30]}...")
                return True
        except Exception as e:
            logger.error(f"数据库错误: 保存搜索结果失败 - {str(e)}")
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
                page = result[0] if result else 1
                logger.debug(f"获取进度: {search_engine} 搜索 '{keyword}' 的当前页码为 {page}")
                return page
        except Exception as e:
            logger.error(f"数据库错误: 获取进度失败 - {str(e)}")
            return 1

    def save_progress(self, keyword: str, search_engine: str, current_page: int, is_done: bool = False) -> bool:
        """保存搜索进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO progress (keyword, search_engine, current_page, is_done)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(keyword, search_engine) 
                    DO UPDATE SET current_page = ?, is_done = ?
                ''', (keyword, search_engine, current_page, is_done, current_page, is_done))
                conn.commit()
                status = "已完成" if is_done else f"进行到第 {current_page} 页"
                logger.debug(f"已更新进度: {search_engine} 搜索 '{keyword}' {status}")
                return True
        except Exception as e:
            logger.error(f"数据库错误: 保存进度失败 - {str(e)}")
            return False

    def get_existing_result(self, url: str) -> Dict[str, Any]:
        """获取已存在的 URL 记录详情"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT keyword, title, is_expired 
                    FROM results 
                    WHERE url = ?
                ''', (url,))
                result = cursor.fetchone()
                if result:
                    return {
                        'keyword': result[0],
                        'title': result[1],
                        'is_expired': bool(result[2])
                    }
                return None
        except Exception as e:
            logger.error(f"数据库错误: 获取 URL 记录失败 - {str(e)}")
            return None 