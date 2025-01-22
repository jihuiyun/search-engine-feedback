import sqlite3
from datetime import datetime
from typing import Dict, Any

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    process_time TIMESTAMP NOT NULL,
                    search_engine TEXT NOT NULL,
                    is_expired BOOLEAN NOT NULL,
                    is_processed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    search_engine TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    last_updated TIMESTAMP NOT NULL
                )
            ''')

    def save_result(self, data: Dict[str, Any]):
        """保存搜索结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO search_results 
                (keyword, title, url, process_time, search_engine, is_expired)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data['keyword'],
                data['title'],
                data['url'],
                datetime.now(),
                data['search_engine'],
                data['is_expired']
            ))

    def save_progress(self, keyword: str, engine: str, page: int):
        """保存处理进度"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO progress 
                (keyword, search_engine, page_number, last_updated)
                VALUES (?, ?, ?, ?)
            ''', (keyword, engine, page, datetime.now()))

    def get_progress(self, keyword: str, engine: str) -> int:
        """获取处理进度"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT page_number FROM progress 
                WHERE keyword = ? AND search_engine = ?
            ''', (keyword, engine))
            result = cursor.fetchone()
            return result[0] if result else 1 