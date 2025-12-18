"""
数据库模块 - 使用SQLite存储微博数据，支持断点续传
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterable, Tuple
from pathlib import Path
from loguru import logger


class Database:
    """微博数据库管理类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 支持字典式访问
        self._init_tables()
        logger.info(f"数据库初始化成功: {db_path}")
    
    def _init_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 微博主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weibos (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at DATETIME,
                text TEXT,
                source TEXT,
                reposts_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                attitudes_count INTEGER DEFAULT 0,
                is_downloaded BOOLEAN DEFAULT 0,
                raw_json TEXT,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                -- 以下字段用于“增量补抓/补标记/断点续传”
                is_retweet INTEGER,
                is_truncated INTEGER DEFAULT 0,
                retweet_category TEXT,
                detail_fetched INTEGER DEFAULT 0
            )
        """)
        
        # 图片表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weibo_id TEXT NOT NULL,
                url TEXT NOT NULL,
                local_path TEXT,
                is_downloaded BOOLEAN DEFAULT 0,
                FOREIGN KEY (weibo_id) REFERENCES weibos(id)
            )
        """)
        
        # 视频表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weibo_id TEXT NOT NULL,
                url TEXT NOT NULL,
                cover_url TEXT,
                local_path TEXT,
                is_downloaded BOOLEAN DEFAULT 0,
                FOREIGN KEY (weibo_id) REFERENCES weibos(id)
            )
        """)
        
        # 进度表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_weibos_user ON weibos(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_weibos_created ON weibos(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_weibo ON images(weibo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_weibo ON videos(weibo_id)")
        
        self.conn.commit()
        logger.info("数据库表结构创建完成")
        self._ensure_weibos_columns()

    def _ensure_weibos_columns(self):
        """
        兼容已有数据库：确保我们需要的列存在。
        注意：只补齐列，不新增“业务之外”的额外列。
        """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(weibos)")
        existing = {row[1] for row in cursor.fetchall()}
        # sqlite 不支持 IF NOT EXISTS 的 ADD COLUMN（不同版本差异），所以手动判断
        alters = []
        if "is_retweet" not in existing:
            alters.append("ALTER TABLE weibos ADD COLUMN is_retweet INTEGER")
        if "is_truncated" not in existing:
            alters.append("ALTER TABLE weibos ADD COLUMN is_truncated INTEGER DEFAULT 0")
        if "retweet_category" not in existing:
            alters.append("ALTER TABLE weibos ADD COLUMN retweet_category TEXT")
        if "detail_fetched" not in existing:
            alters.append("ALTER TABLE weibos ADD COLUMN detail_fetched INTEGER DEFAULT 0")

        for sql in alters:
            cursor.execute(sql)
        if alters:
            self.conn.commit()
    
    def save_weibo(self, weibo_data: Dict[str, Any]) -> bool:
        """
        保存微博数据
        
        Args:
            weibo_data: 微博数据字典
            
        Returns:
            是否保存成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO weibos 
                (id, user_id, created_at, text, source, reposts_count, comments_count, attitudes_count, raw_json,
                 is_retweet, is_truncated, retweet_category, detail_fetched)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                weibo_data['id'],
                weibo_data['user_id'],
                weibo_data.get('created_at'),
                weibo_data.get('text'),
                weibo_data.get('source'),
                weibo_data.get('reposts_count', 0),
                weibo_data.get('comments_count', 0),
                weibo_data.get('attitudes_count', 0),
                json.dumps(weibo_data, ensure_ascii=False),
                weibo_data.get("is_retweet"),
                1 if weibo_data.get("is_truncated") else 0,
                weibo_data.get("retweet_category"),
                1 if weibo_data.get("detail_fetched") else 0,
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存微博失败 {weibo_data.get('id')}: {e}")
            return False
    
    def save_image(self, weibo_id: str, url: str, local_path: Optional[str] = None) -> int:
        """
        保存图片记录
        
        Args:
            weibo_id: 微博ID
            url: 图片URL
            local_path: 本地保存路径
            
        Returns:
            图片记录ID
        """
        cursor = self.conn.cursor()
        # 去重：避免重复插入同一 weibo_id + url
        cursor.execute("SELECT id FROM images WHERE weibo_id = ? AND url = ? LIMIT 1", (weibo_id, url))
        row = cursor.fetchone()
        if row:
            return int(row["id"]) if isinstance(row, sqlite3.Row) else int(row[0])
        cursor.execute(
            "INSERT INTO images (weibo_id, url, local_path, is_downloaded) VALUES (?, ?, ?, ?)",
            (weibo_id, url, local_path, 1 if local_path else 0),
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def save_video(self, weibo_id: str, url: str, cover_url: Optional[str] = None, 
                   local_path: Optional[str] = None) -> int:
        """
        保存视频记录
        
        Args:
            weibo_id: 微博ID
            url: 视频URL
            cover_url: 封面URL
            local_path: 本地保存路径
            
        Returns:
            视频记录ID
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM videos WHERE weibo_id = ? AND url = ? LIMIT 1", (weibo_id, url))
        row = cursor.fetchone()
        if row:
            return int(row["id"]) if isinstance(row, sqlite3.Row) else int(row[0])
        cursor.execute(
            "INSERT INTO videos (weibo_id, url, cover_url, local_path, is_downloaded) VALUES (?, ?, ?, ?, ?)",
            (weibo_id, url, cover_url, local_path, 1 if local_path else 0),
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_image_path(self, image_id: int, local_path: str):
        """更新图片本地路径"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE images SET local_path = ?, is_downloaded = 1 
            WHERE id = ?
        """, (local_path, image_id))
        self.conn.commit()
    
    def update_video_path(self, video_id: int, local_path: str):
        """更新视频本地路径"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE videos SET local_path = ?, is_downloaded = 1 
            WHERE id = ?
        """, (local_path, video_id))
        self.conn.commit()
    
    def get_undownloaded_images(self) -> List[Dict]:
        """获取未下载的图片列表"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE is_downloaded = 0 OR local_path IS NULL")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_undownloaded_videos(self) -> List[Dict]:
        """获取未下载的视频列表"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE is_downloaded = 0 OR local_path IS NULL")
        return [dict(row) for row in cursor.fetchall()]

    def weibo_exists(self, weibo_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM weibos WHERE id = ? LIMIT 1", (weibo_id,))
        return cursor.fetchone() is not None

    def get_weibo_brief(self, weibo_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, text, raw_json, is_retweet, is_truncated, retweet_category, detail_fetched FROM weibos WHERE id = ?",
            (weibo_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_weibos_needing_detail(self, limit: int = 200) -> List[str]:
        """
        需要抓取详情页的微博（用于补全文/补图片/补分类），基于 checkpoint 防重复。
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM weibos WHERE is_truncated = 1 AND (detail_fetched IS NULL OR detail_fetched = 0) ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [row["id"] for row in cursor.fetchall()]

    def list_weibos_missing_retweet_flag(self, limit: int = 500) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, text, detail_fetched FROM weibos WHERE is_retweet IS NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_weibos_detail_unfetched_before_year(self, *, before_year: int, limit: int = 500) -> List[str]:
        """
        历史回填：选择年份 < before_year 且 detail_fetched=0/NULL 的微博（不区分是否折叠/原创/转发）。
        例如 before_year=2020 表示回填 2019 及以前。
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id FROM weibos
            WHERE (detail_fetched IS NULL OR detail_fetched = 0)
              AND CAST(substr(created_at, 1, 4) AS int) < ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(before_year), int(limit)),
        )
        return [row["id"] for row in cursor.fetchall()]

    def list_retweet_recheck_candidates_before_year(
        self,
        *,
        before_year: int,
        limit: int = 500,
        mode: str = "video_phrase",
    ) -> List[str]:
        """
        方案A 纠错候选：选择年份 < before_year 的微博。
        - video_phrase: 只复核 text 含“微博视频”等尾巴的 is_retweet=0（更省）
        - all_original: 复核该范围内所有 is_retweet=0（更全面）
        """
        cursor = self.conn.cursor()
        if mode == "all_original":
            cursor.execute(
                """
                SELECT id FROM weibos
                WHERE CAST(substr(created_at, 1, 4) AS int) < ?
                  AND is_retweet = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(before_year), int(limit)),
            )
        else:
            cursor.execute(
                """
                SELECT id FROM weibos
                WHERE CAST(substr(created_at, 1, 4) AS int) < ?
                  AND is_retweet = 0
                  AND (text LIKE '%的微博视频%' OR text LIKE '%微博视频%')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(before_year), int(limit)),
            )
        return [row["id"] for row in cursor.fetchall()]

    def list_retweet_recheck_candidates(
        self,
        *,
        year: int,
        limit: int = 500,
        mode: str = "video_phrase",
    ) -> List[str]:
        """
        用于“方案A：纠错现有数据库”的候选集。
        - video_phrase: 只复核 text 中包含“的微博视频”的、当前被标为原创(is_retweet=0)的微博（典型结构型转发）
        - all_original: 复核该年份所有 is_retweet=0 的微博（更全面但网络请求更多）
        """
        cursor = self.conn.cursor()
        y = str(year)
        if mode == "all_original":
            cursor.execute(
                """
                SELECT id FROM weibos
                WHERE created_at LIKE ? AND is_retweet = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"{y}-%", int(limit)),
            )
        else:
            cursor.execute(
                """
                SELECT id FROM weibos
                WHERE created_at LIKE ? AND is_retweet = 0
                  AND (text LIKE '%的微博视频%' OR text LIKE '%微博视频%')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"{y}-%", int(limit)),
            )
        return [row["id"] for row in cursor.fetchall()]

    def update_weibo_fields(self, weibo_id: str, fields: Dict[str, Any]) -> None:
        """
        按需更新 weibos 的部分字段（用于增量补抓）。
        """
        if not fields:
            return
        allowed = {
            "text",
            "raw_json",
            "is_retweet",
            "is_truncated",
            "retweet_category",
            "detail_fetched",
            "fetched_at",
        }
        bad = set(fields.keys()) - allowed
        if bad:
            raise ValueError(f"不允许更新字段: {sorted(bad)}")
        parts = []
        params: List[Any] = []
        for k, v in fields.items():
            parts.append(f"{k} = ?")
            params.append(v)
        params.append(weibo_id)
        sql = f"UPDATE weibos SET {', '.join(parts)} WHERE id = ?"
        cursor = self.conn.cursor()
        cursor.execute(sql, tuple(params))
        self.conn.commit()
    
    def get_all_weibos(self, order_by: str = "created_at DESC") -> List[Dict]:
        """
        获取所有微博
        
        Args:
            order_by: 排序方式
            
        Returns:
            微博列表
        """
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM weibos ORDER BY {order_by}")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_weibo_images(self, weibo_id: str) -> List[Dict]:
        """获取指定微博的图片"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE weibo_id = ?", (weibo_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_weibo_videos(self, weibo_id: str) -> List[Dict]:
        """获取指定微博的视频"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE weibo_id = ?", (weibo_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_progress(self, key: str) -> Optional[str]:
        """获取进度信息"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM progress WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None
    
    def set_progress(self, key: str, value: str):
        """设置进度信息"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO progress (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        self.conn.commit()
    
    def get_statistics(self) -> Dict[str, int]:
        """获取统计信息"""
        cursor = self.conn.cursor()
        
        stats = {}
        cursor.execute("SELECT COUNT(*) as count FROM weibos")
        stats['total_weibos'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM images")
        stats['total_images'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM images WHERE is_downloaded = 1")
        stats['downloaded_images'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        stats['total_videos'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM videos WHERE is_downloaded = 1")
        stats['downloaded_videos'] = cursor.fetchone()['count']
        
        return stats
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()
        logger.info("数据库连接已关闭")

