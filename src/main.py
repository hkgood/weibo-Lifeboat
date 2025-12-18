"""
微博备份系统 - 主程序入口
"""
import asyncio
import json
import sys
from pathlib import Path
from loguru import logger
from tqdm import tqdm

from database import Database
from weibo_fetcher import WeiboFetcher
from media_downloader import MediaDownloader
from html_generator import HTMLGenerator


class WeiboBackup:
    """微博备份主类"""
    
    def __init__(self, config_path: str = 'config.json'):
        """
        初始化备份系统
        
        Args:
            config_path: 配置文件路径
        """
        # 配置日志
        logger.remove()
        logger.add(sys.stdout, level="INFO", 
                  format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
        logger.add("data/backup.log", level="DEBUG", rotation="10 MB")
        
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 初始化各模块
        weibo_config = self.config['weibo']
        crawler_config = self.config['crawler']
        storage_config = self.config['storage']
        
        self.db = Database(storage_config['database_path'])
        
        self.fetcher = WeiboFetcher(
            user_id=weibo_config['user_id'],
            cookie=weibo_config['cookie'],
            user_agent=weibo_config['user_agent'],
            config=crawler_config
        )
        
        self.downloader = MediaDownloader(
            config=storage_config,
            headers={
                'User-Agent': weibo_config['user_agent'],
                'Referer': 'https://m.weibo.cn/'
            }
        )
        
        self.html_generator = HTMLGenerator(config=storage_config)
        
        logger.info("=" * 60)
        logger.info("微博备份系统已启动")
        logger.info("=" * 60)
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"配置文件不存在: {config_path}")
            logger.error("请复制 config.example.json 为 config.json 并填写配置")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            sys.exit(1)
    
    async def run(self):
        """执行完整的备份流程"""
        try:
            # 步骤1: 测试连接
            logger.info("\n[步骤 1/4] 测试连接...")
            if not await self.fetcher.test_connection():
                logger.error("连接测试失败，请检查Cookie是否有效")
                return
            
            # 步骤2: 抓取微博数据
            logger.info("\n[步骤 2/4] 抓取微博数据...")
            await self._fetch_weibos()
            
            # 步骤3: 下载媒体文件
            logger.info("\n[步骤 3/4] 下载媒体文件...")
            await self._download_media()
            
            # 步骤4: 生成HTML
            logger.info("\n[步骤 4/4] 生成HTML备份页面...")
            self._generate_html()
            
            # 显示统计信息
            self._show_statistics()
            
            logger.info("\n" + "=" * 60)
            logger.info("✓ 备份完成！")
            logger.info("=" * 60)
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断，保存进度...")
            self.db.close()
            logger.info("进度已保存，下次运行将继续")
        except Exception as e:
            logger.exception(f"备份过程出错: {e}")
        finally:
            self.db.close()
    
    async def _fetch_weibos(self):
        """抓取微博数据"""
        # 检查断点续传
        last_page = self.db.get_progress('last_page')
        start_page = int(last_page) + 1 if last_page else 1
        
        if start_page > 1:
            logger.info(f"从第 {start_page} 页继续抓取（断点续传）")
        
        # 抓取数据
        weibos = await self.fetcher.fetch_all_weibos(start_page=start_page)
        
        if not weibos:
            logger.warning("没有抓取到新的微博数据")
            return
        
        # 保存到数据库
        logger.info(f"保存微博数据到数据库...")
        
        with tqdm(total=len(weibos), desc="保存微博") as pbar:
            for weibo in weibos:
                # 保存微博
                self.db.save_weibo(weibo)
                
                # 保存图片记录
                for img_url in weibo.get('images', []):
                    self.db.save_image(weibo['id'], img_url)
                
                # 保存视频记录
                for video in weibo.get('videos', []):
                    self.db.save_video(weibo['id'], video['url'], video.get('cover'))
                
                pbar.update(1)
        
        logger.info(f"✓ 微博数据保存完成")
    
    async def _download_media(self):
        """下载媒体文件"""
        # 下载图片
        images = self.db.get_undownloaded_images()
        if images:
            logger.info(f"待下载图片: {len(images)} 张")
            
            with tqdm(total=len(images), desc="下载图片") as pbar:
                results = await self.downloader.download_images_batch(images)
                
                # 更新数据库
                for image_id, local_path in results:
                    if local_path:
                        self.db.update_image_path(image_id, local_path)
                    pbar.update(1)
        else:
            logger.info("所有图片已下载")
        
        # 下载视频
        videos = self.db.get_undownloaded_videos()
        if videos:
            logger.info(f"待下载视频: {len(videos)} 个")
            
            with tqdm(total=len(videos), desc="下载视频") as pbar:
                results = await self.downloader.download_videos_batch(videos)
                
                # 更新数据库
                for video_id, local_path in results:
                    if local_path:
                        self.db.update_video_path(video_id, local_path)
                    pbar.update(1)
        else:
            logger.info("所有视频已下载")
        
        logger.info("✓ 媒体文件下载完成")
    
    def _generate_html(self):
        """生成HTML备份页面"""
        # 获取所有微博
        weibos = self.db.get_all_weibos(order_by="created_at DESC")
        
        if not weibos:
            logger.warning("数据库中没有微博数据")
            return
        
        # 构建图片和视频映射
        images_map = {}
        videos_map = {}
        
        for weibo in weibos:
            weibo_id = weibo['id']
            images_map[weibo_id] = self.db.get_weibo_images(weibo_id)
            videos_map[weibo_id] = self.db.get_weibo_videos(weibo_id)
        
        # 获取统计信息
        stats = self.db.get_statistics()
        
        # 生成HTML
        output_file = self.html_generator.generate(weibos, images_map, videos_map, stats)
        
        logger.info(f"✓ HTML文件: {output_file}")
    
    def _show_statistics(self):
        """显示统计信息"""
        stats = self.db.get_statistics()
        
        logger.info("\n" + "=" * 60)
        logger.info("备份统计")
        logger.info("=" * 60)
        logger.info(f"微博总数: {stats['total_weibos']} 条")
        logger.info(f"图片总数: {stats['total_images']} 张 (已下载: {stats['downloaded_images']})")
        logger.info(f"视频总数: {stats['total_videos']} 个 (已下载: {stats['downloaded_videos']})")
        
        # 计算存储空间
        data_dir = Path(self.config['storage']['images_dir']).parent
        if data_dir.exists():
            total_size = sum(f.stat().st_size for f in data_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            logger.info(f"占用空间: {size_mb:.2f} MB")
        
        logger.info("=" * 60)


async def main():
    """主函数"""
    backup = WeiboBackup()
    await backup.run()


if __name__ == '__main__':
    # 运行异步主函数
    asyncio.run(main())

