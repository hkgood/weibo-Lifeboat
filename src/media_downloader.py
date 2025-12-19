"""
媒体文件下载模块 - 异步下载图片和视频
"""
import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import httpx
from loguru import logger
import aiofiles


class MediaDownloader:
    """媒体文件下载器"""
    
    def __init__(self, config: Dict, headers: Dict):
        """
        初始化下载器
        
        Args:
            config: 配置信息
            headers: HTTP请求头
        """
        self.config = config
        self.headers = headers
        self.images_dir = Path(config['images_dir'])
        self.videos_dir = Path(config['videos_dir'])
        
        # 创建目录
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        # 延迟创建信号量（避免在没有event loop的线程中初始化）
        self._semaphore = None
        self._concurrent_downloads = config.get('concurrent_downloads', 20)
        
        logger.info(f"MediaDownloader 初始化完成")
        logger.info(f"图片目录: {self.images_dir}")
        logger.info(f"视频目录: {self.videos_dir}")
    
    @property
    def semaphore(self):
        """延迟创建信号量，确保在有event loop的上下文中创建"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._concurrent_downloads)
        return self._semaphore
    
    async def download_file(self, url: str, save_path: Path, retry: int = 3) -> bool:
        """
        下载单个文件
        
        Args:
            url: 文件URL
            save_path: 保存路径
            retry: 重试次数
            
        Returns:
            是否下载成功
        """
        async with self.semaphore:
            for attempt in range(retry):
                try:
                    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                        response = await client.get(url, headers=self.headers)
                        
                        if response.status_code == 200:
                            async with aiofiles.open(save_path, 'wb') as f:
                                await f.write(response.content)
                            
                            logger.debug(f"下载成功: {save_path.name}")
                            return True
                        else:
                            logger.warning(f"下载失败 ({response.status_code}): {url}")
                            
                except Exception as e:
                    logger.warning(f"下载出错 (尝试 {attempt + 1}/{retry}): {e}")
                    if attempt < retry - 1:
                        await asyncio.sleep(1)
            
            logger.error(f"下载失败（已重试{retry}次）: {url}")
            return False
    
    async def download_image(self, image_id: int, url: str, weibo_id: str, 
                            index: int) -> Tuple[int, Optional[str]]:
        """
        下载图片
        
        Args:
            image_id: 图片记录ID
            url: 图片URL
            weibo_id: 微博ID
            index: 图片索引
            
        Returns:
            (图片ID, 本地路径) 或 (图片ID, None)
        """
        # 从URL提取文件扩展名
        ext = self._get_file_extension(url, default='jpg')
        filename = f"{weibo_id}_{index}.{ext}"
        save_path = self.images_dir / filename
        
        # 如果已存在，跳过
        if save_path.exists():
            logger.debug(f"图片已存在，跳过: {filename}")
            return (image_id, str(save_path.relative_to(save_path.parent.parent)))
        
        success = await self.download_file(url, save_path)
        
        if success:
            relative_path = str(save_path.relative_to(save_path.parent.parent))
            return (image_id, relative_path)
        else:
            return (image_id, None)
    
    async def download_video(self, video_id: int, url: str, weibo_id: str,
                            index: int) -> Tuple[int, Optional[str]]:
        """
        下载视频
        
        Args:
            video_id: 视频记录ID
            url: 视频URL
            weibo_id: 微博ID
            index: 视频索引
            
        Returns:
            (视频ID, 本地路径) 或 (视频ID, None)
        """
        ext = self._get_file_extension(url, default='mp4')
        filename = f"{weibo_id}_{index}.{ext}"
        save_path = self.videos_dir / filename
        
        # 如果已存在，跳过
        if save_path.exists():
            logger.debug(f"视频已存在，跳过: {filename}")
            return (video_id, str(save_path.relative_to(save_path.parent.parent)))
        
        success = await self.download_file(url, save_path)
        
        if success:
            relative_path = str(save_path.relative_to(save_path.parent.parent))
            return (video_id, relative_path)
        else:
            return (video_id, None)
    
    async def download_images_batch(
        self,
        images: List[Dict],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Tuple[int, Optional[str]]]:
        """
        批量下载图片
        
        Args:
            images: 图片记录列表
            
        Returns:
            下载结果列表
        """
        tasks: List[asyncio.Task] = []
        weibo_images = {}  # 按微博ID分组，用于计算索引
        
        # 按微博分组
        for img in images:
            weibo_id = img['weibo_id']
            if weibo_id not in weibo_images:
                weibo_images[weibo_id] = []
            weibo_images[weibo_id].append(img)
        
        # 创建下载任务
        for weibo_id, imgs in weibo_images.items():
            for idx, img in enumerate(imgs):
                coro = self.download_image(img["id"], img["url"], weibo_id, idx)
                tasks.append(asyncio.create_task(coro))
        
        logger.info(f"开始下载 {len(tasks)} 张图片...")
        total = len(tasks)
        done = 0
        valid_results: List[Tuple[int, Optional[str]]] = []
        for fut in asyncio.as_completed(tasks):
            try:
                result = await fut
                valid_results.append(result)
            except Exception as e:
                logger.error(f"下载任务异常: {e}")
            finally:
                done += 1
                if progress_cb:
                    try:
                        progress_cb(done, total)
                    except Exception:
                        pass
        
        success_count = sum(1 for _, path in valid_results if path is not None)
        logger.info(f"图片下载完成: {success_count}/{len(tasks)} 成功")
        
        return valid_results
    
    async def download_videos_batch(
        self,
        videos: List[Dict],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Tuple[int, Optional[str]]]:
        """
        批量下载视频
        
        Args:
            videos: 视频记录列表
            
        Returns:
            下载结果列表
        """
        tasks: List[asyncio.Task] = []
        weibo_videos = {}  # 按微博ID分组
        
        # 按微博分组
        for vid in videos:
            weibo_id = vid['weibo_id']
            if weibo_id not in weibo_videos:
                weibo_videos[weibo_id] = []
            weibo_videos[weibo_id].append(vid)
        
        # 创建下载任务
        for weibo_id, vids in weibo_videos.items():
            for idx, vid in enumerate(vids):
                coro = self.download_video(vid["id"], vid["url"], weibo_id, idx)
                tasks.append(asyncio.create_task(coro))
        
        logger.info(f"开始下载 {len(tasks)} 个视频...")
        total = len(tasks)
        done = 0
        valid_results: List[Tuple[int, Optional[str]]] = []
        for fut in asyncio.as_completed(tasks):
            try:
                result = await fut
                valid_results.append(result)
            except Exception as e:
                logger.error(f"下载任务异常: {e}")
            finally:
                done += 1
                if progress_cb:
                    try:
                        progress_cb(done, total)
                    except Exception:
                        pass
        
        success_count = sum(1 for _, path in valid_results if path is not None)
        logger.info(f"视频下载完成: {success_count}/{len(tasks)} 成功")
        
        return valid_results
    
    def _get_file_extension(self, url: str, default: str = 'jpg') -> str:
        """
        从URL提取文件扩展名
        
        Args:
            url: 文件URL
            default: 默认扩展名
            
        Returns:
            文件扩展名
        """
        try:
            path = Path(url.split('?')[0])  # 移除query参数
            ext = path.suffix.lstrip('.')
            return ext if ext else default
        except:
            return default

