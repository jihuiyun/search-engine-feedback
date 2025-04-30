import sqlite3
import logging
import time
from typing import Dict, Any
import traceback

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
    logging.info("成功导入 mysql.connector 模块")
except ImportError:
    MYSQL_AVAILABLE = False
    logging.warning("mysql-connector-python 未安装，将尝试使用 PyMySQL")
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
        MYSQL_AVAILABLE = True
    except ImportError:
        logging.error("无法导入 MySQL 连接库，请安装 mysql-connector-python 或 pymysql")

logger = logging.getLogger(__name__)

class Database:

    def _get_safe_config(self):
        """返回不含密码的配置信息，用于日志输出"""
        safe_config = self.mysql_config.copy()
        if 'password' in safe_config:
            safe_config['password'] = '******'
        return safe_config


    def __init__(self, config):
        """初始化数据库连接"""
        logger.info("初始化数据库连接...")
        self.sqlite_path = config.get('path', 'search_results.db')
        logger.info(f"SQLite 数据库路径: {self.sqlite_path}")
        
        # MySQL 配置
        self.mysql_config = {
            'host': '10.30.40.108',
            'port': 3906,
            'database': 'network_qa',
            'user': config.get('mysql_user', ''),
            'password': config.get('mysql_password', ''),
            'connect_timeout': 10
        }
        
        # 初始化 SQLite 数据库(用于progress表)
        logger.info("开始初始化 SQLite 数据库...")
        self.init_sqlite_db()
        logger.info("SQLite 数据库初始化完成")
        
        # 测试 MySQL 连接并输出详细的连接信息用于调试
        logger.info("准备测试 MySQL 连接...")
        self.mysql_available = False
        try:
            logger.info("开始测试 MySQL 连接...")
            self._test_mysql_connection()
            self.mysql_available = True
            logger.info("MySQL 连接测试成功，将使用 MySQL 作为主数据库")
            print("MySQL 连接测试成功，将使用 MySQL 作为主数据库")
        except Exception as e:
            logger.error(f"MySQL 连接测试失败，将只使用 SQLite: {str(e)}")
            logger.error(traceback.format_exc())
            logger.info("将使用 SQLite 作为备用数据库")

    def init_sqlite_db(self):
        """初始化SQLite数据库表"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
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
                    logger.info("SQLite数据库初始化: 已创建 progress 表")
                
                conn.commit()
        except Exception as e:
            logger.error(f"初始化 SQLite 数据库失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _get_mysql_connection(self):
        """获取MySQL连接，添加重试机制"""
        if not MYSQL_AVAILABLE:
            logger.error("MySQL 连接库未安装")
            raise Exception("MySQL 连接库未安装")
            
        max_retries = 3
        retry_count = 0
        
        logger.info("开始获取MySQL连接...")
        logger.info(f"全局模块: {[key for key in globals().keys() if not key.startswith('_')]}")
        
        while retry_count < max_retries:
            try:
                if 'mysql' in globals():
                    logger.info("使用 mysql 模块连接数据库")
                    config = self.mysql_config.copy()
                    config['consume_results'] = True
                    return mysql.connector.connect(**config)
                elif 'mysql_connector' in globals():
                    logger.info("使用 PyMySQL(MySQLdb) 模块连接数据库")
                    return mysql_connector.connect(**self.mysql_config)
                else:
                    logger.error("没有可用的MySQL连接模块")
                    raise Exception("没有可用的MySQL连接模块")
            except Exception as e:
                retry_count += 1
                logger.warning(f"MySQL 连接失败 (尝试 {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    logger.error(f"MySQL 连接失败，已达到最大重试次数: {str(e)}")
                    logger.error(f"连接参数: {self._get_safe_config()}")
                    raise
                time.sleep(1)  # 等待1秒后重试
    

    
    def _test_mysql_connection(self):
        """测试MySQL连接是否可用"""
        try:
            logger.info(f"开始测试 MySQL 连接: {self._get_safe_config()}")
            logger.info(f"MySQL 可用状态: {MYSQL_AVAILABLE}")
            
            conn = self._get_mysql_connection()
            logger.info("MySQL 连接成功获取")
            print("MySQL 连接成功获取")
            # 测试表结构
            cursor = conn.cursor()
            try:
                logger.info("正在查询表结构...")
                cursor.execute("SHOW COLUMNS FROM search_engine_feedback_results")
                columns = cursor.fetchall()
                column_names = [col[0] for col in columns]
                logger.info(f"MySQL 表结构: {column_names}")
                
                # 验证必要的列是否存在
                required_columns = ['key_word', 'search_engine', 'url', 'title', 'is_expired']
                missing_columns = [col for col in required_columns if col not in column_names]
                
                if missing_columns:
                    logger.warning(f"MySQL 表缺少必要的列: {missing_columns}")
            except Exception as e:
                logger.error(f"无法查询表结构: {str(e)}")
                logger.error(traceback.format_exc())
            
            cursor.close()
            conn.close()
            logger.info("MySQL 连接和表结构测试成功")
        except Exception as e:
            logger.error(f"测试 MySQL 连接失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def save_result(self, result: Dict[str, Any]) -> bool:
        """保存搜索结果，根据可用性选择 MySQL 或 SQLite"""
        if self.mysql_available:
            return self._save_result_mysql(result)
        else:
            return self._save_result_sqlite(result)
    
    def _save_result_mysql(self, result: Dict[str, Any]) -> bool:
        """保存搜索结果到 MySQL"""
        conn = None
        try:
            conn = self._get_mysql_connection()
            cursor = conn.cursor()
            
            # 记录操作详情，方便调试
            logger.debug(f"保存到 MySQL - 关键词: {result['keyword']}, URL: {result['url'][:30]}...")
            
            # 先检查是否存在记录
            check_query = """
                SELECT sysid FROM search_engine_feedback_results 
                WHERE key_word = %s AND search_engine = %s AND url = %s
            """
            cursor.execute(check_query, (
                result['keyword'],
                result['search_engine'],
                result['url']
            ))
            
            existing = cursor.fetchone()
            
            if not existing:
                # 不存在则插入
                insert_query = """
                    INSERT INTO search_engine_feedback_results 
                    (key_word, title, url, search_engine, is_expired, last_updated) 
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(insert_query, (
                    result['keyword'],
                    result['title'],
                    result['url'],
                    result['search_engine'],
                    1 if result['is_expired'] else 0
                ))
                logger.debug(f"MySQL: 插入新记录 - {result['title'][:20]}...")
            else:
                # 存在则更新
                update_query = """
                    UPDATE search_engine_feedback_results 
                    SET is_expired = %s, last_updated = NOW()
                    WHERE key_word = %s AND search_engine = %s AND url = %s
                """
                cursor.execute(update_query, (
                    1 if result['is_expired'] else 0,
                    result['keyword'],
                    result['search_engine'],
                    result['url']
                ))
                logger.debug(f"MySQL: 更新记录 - {result['title'][:20]}...")
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存到 MySQL 失败: {str(e)}")
            logger.error(traceback.format_exc())
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _save_result_sqlite(self, result: Dict[str, Any]) -> bool:
        """保存搜索结果到 SQLite (后备方案)"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 检查结果表是否存在
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='results'
                """)
                
                # 如果不存在，创建表
                if not cursor.fetchone():
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
                
                # 检查是否存在记录
                cursor.execute('''
                    SELECT id FROM results 
                    WHERE keyword = ? AND search_engine = ? AND url = ?
                ''', (result['keyword'], result['search_engine'], result['url']))
                
                if not cursor.fetchone():
                    # 不存在则插入
                    cursor.execute('''
                        INSERT INTO results (
                            keyword, title, url, search_engine, is_expired, last_updated
                        ) VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ''', (
                        result['keyword'],
                        result['title'],
                        result['url'],
                        result['search_engine'],
                        result['is_expired']
                    ))
                else:
                    # 存在则更新
                    cursor.execute('''
                        UPDATE results 
                        SET is_expired = ?, last_updated = datetime('now')
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
            logger.error(f"保存到 SQLite 失败: {str(e)}")
            return False

    def get_existing_result(self, url: str = None, keyword: str = None, search_engine: str = None, title: str = None) -> Dict[str, Any]:
        """获取已存在的结果，根据可用性选择 MySQL 或 SQLite"""
        if self.mysql_available:
            return self._get_existing_result_mysql(url, keyword, search_engine, title)
        else:
            return self._get_existing_result_sqlite(url, keyword, search_engine, title)
    
    def _get_existing_result_mysql(self, url: str = None, keyword: str = None, search_engine: str = None, title: str = None) -> Dict[str, Any]:
        """从 MySQL 获取结果"""
        conn = None
        try:
            conn = self._get_mysql_connection()
            cursor = conn.cursor()
            
            if url:
                query = """
                    SELECT key_word, title, is_expired 
                    FROM search_engine_feedback_results 
                    WHERE url = %s
                """
                cursor.execute(query, (url,))
            elif keyword and search_engine and title:
                query = """
                    SELECT key_word, title, is_expired 
                    FROM search_engine_feedback_results 
                    WHERE key_word = %s AND search_engine = %s AND title = %s
                """
                cursor.execute(query, (keyword, search_engine, title))
            else:
                return None
            
            result = cursor.fetchone()
            if result:
                return {
                    'keyword': result[0],
                    'title': result[1],
                    'is_expired': bool(result[2])
                }
            return None
        except Exception as e:
            logger.error(f"从 MySQL 获取结果失败: {str(e)}")
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _get_existing_result_sqlite(self, url: str = None, keyword: str = None, search_engine: str = None, title: str = None) -> Dict[str, Any]:
        """从 SQLite 获取结果 (后备方案)"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 先检查表是否存在
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='results'
                """)
                
                if not cursor.fetchone():
                    # 表不存在，返回None
                    return None
                
                if url:
                    cursor.execute('''
                        SELECT keyword, title, is_expired 
                        FROM results 
                        WHERE url = ?
                    ''', (url,))
                elif keyword and search_engine and title:
                    cursor.execute('''
                        SELECT keyword, title, is_expired 
                        FROM results 
                        WHERE keyword = ? AND search_engine = ? AND title = ?
                    ''', (keyword, search_engine, title))
                else:
                    return None
                
                result = cursor.fetchone()
                if result:
                    return {
                        'keyword': result[0],
                        'title': result[1],
                        'is_expired': bool(result[2])
                    }
                return None
        except Exception as e:
            logger.error(f"从 SQLite 获取结果失败: {str(e)}")
            return None
    
    def check_keyword_done(self, keyword: str, search_engine: str) -> bool:
        """检查关键词是否已处理完成 (SQLite)"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT is_done 
                    FROM progress 
                    WHERE keyword = ? AND search_engine = ?
                ''', (keyword, search_engine))
                result = cursor.fetchone()
                return bool(result[0]) if result else False
        except Exception as e:
            logger.error(f"检查关键词状态失败: {str(e)}")
            return False
            
    def save_progress(self, keyword: str, search_engine: str, is_done: bool = False) -> bool:
        """保存处理进度 (SQLite)"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO progress (keyword, search_engine, is_done)
                    VALUES (?, ?, ?)
                    ON CONFLICT(keyword, search_engine) 
                    DO UPDATE SET 
                        is_done = ?
                ''', (keyword, search_engine, is_done, is_done))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存进度失败: {str(e)}")
            return False

    def check_url_exists(self, url: str) -> bool:
        """检查 URL 是否已经处理过"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
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

    def get_progress(self, keyword: str, search_engine: str) -> int:
        """获取搜索进度"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
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