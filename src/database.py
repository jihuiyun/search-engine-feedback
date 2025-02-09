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
            
            # 创建新的 progress 表
            if not cursor.fetchone():
                cursor.execute('''
                    CREATE TABLE progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL,
                        search_engine TEXT NOT NULL,
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

    def save_result(self, result: Dict[str, Any]) -> bool:
        """保存搜索结果（添加去重逻辑）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 检查是否存在相同记录
                cursor.execute('''
                    SELECT id FROM results 
                    WHERE keyword = ? AND search_engine = ? AND url = ?
                ''', (result['keyword'], result['search_engine'], result['url']))
                
                if cursor.fetchone() is None:
                    # 不存在则插入新记录
                    cursor.execute('''
                        INSERT INTO results (
                            keyword, search_engine, url, title, 
                            is_expired, last_updated
                        ) VALUES (?, ?, ?, ?, ?, datetime('now', '+8 hours'))
                    ''', (
                        result['keyword'],
                        result['search_engine'],
                        result['url'],
                        result['title'],
                        result['is_expired']
                    ))
                else:
                    # 存在则更新记录
                    cursor.execute('''
                        UPDATE results 
                        SET is_expired = ?, last_updated = datetime('now', '+8 hours')
                        WHERE keyword = ? AND search_engine = ? AND url = ?
                    ''', (
                        result['is_expired'],
                        result['keyword'],
                        result['search_engine'],
                        result['url']
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
                page = result[0] if result else 1
                logger.debug(f"获取进度: {search_engine} 搜索 '{keyword}' 的当前页码为 {page}")
                return page
        except Exception as e:
            logger.error(f"数据库错误: 获取进度失败 - {str(e)}")
            return 1

    def save_progress(self, keyword: str, search_engine: str, is_done: bool = False) -> bool:
        """保存搜索进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO progress (keyword, search_engine, is_done)
                    VALUES (?, ?, ?)
                    ON CONFLICT(keyword, search_engine) 
                    DO UPDATE SET 
                        is_done = ?
                ''', (keyword, search_engine, is_done, is_done))
                conn.commit()
                status = "已完成" if is_done else "进行中"
                logger.debug(f"已更新进度: {search_engine} 搜索 '{keyword}' {status}")
                return True
        except Exception as e:
            logger.error(f"数据库错误: 保存进度失败 - {str(e)}")
            return False

    def get_existing_result(self, url: str = None, keyword: str = None, search_engine: str = None, title: str = None) -> Dict[str, Any]:
        """获取已存在的 URL 记录详情"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if url:
                    # 如果提供了 url 则进行精确匹配
                    cursor.execute('''
                        SELECT keyword, title, is_expired 
                        FROM results 
                        WHERE url = ?
                    ''', (url,))
                elif keyword and search_engine and title:
                    # 如果提供了关键词、搜索引擎和标题，则进行精确匹配
                    cursor.execute('''
                        SELECT keyword, title, is_expired 
                        FROM results 
                        WHERE keyword = ? AND search_engine = ? AND title = ?
                    ''', (keyword, search_engine, title))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'keyword': result[0],
                        'title': result[1],
                        'is_expired': bool(result[2])
                    }
                return None
        except Exception as e:
            logger.error(f"数据库错误: 获取记录失败 - {str(e)}")
            return None

    def check_keyword_done(self, keyword: str, search_engine: str) -> bool:
        """检查关键词是否已处理完成"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT is_done 
                    FROM progress 
                    WHERE keyword = ? AND search_engine = ?
                ''', (keyword, search_engine))
                result = cursor.fetchone()
                return bool(result[0]) if result else False
        except Exception as e:
            logger.error(f"数据库错误: 检查关键词完成状态失败 - {str(e)}")
            return False 