"""
微博爬取模块 - 从m.weibo.cn抓取微博数据
"""
import asyncio
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from loguru import logger


class WeiboFetcher:
    """微博数据抓取器"""
    
    def __init__(self, user_id: str, cookie: str, user_agent: str, config: Dict):
        """
        初始化抓取器
        
        Args:
            user_id: 用户ID
            cookie: Cookie字符串
            user_agent: User-Agent
            config: 配置信息
        """
        self.user_id = user_id
        self.cookie = cookie
        self.user_agent = user_agent
        self.config = config
        self.request_delay = config.get('request_delay', 2.0)
        self.timeout = config.get('timeout', 30)
        
        # 构建headers
        self.headers = {
            'User-Agent': user_agent,
            'Cookie': cookie,
            'Referer': f'https://weibo.cn/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        self.base_url = 'https://weibo.cn'
        logger.info(f"WeiboFetcher 初始化完成，用户ID: {user_id}")
    
    async def fetch_user_weibos(self, page: int = 1) -> Optional[Dict[str, Any]]:
        """
        获取用户微博列表（HTML解析方式）
        
        Args:
            page: 页码
            
        Returns:
            解析后的数据
        """
        # 使用个人主页URL（不使用/profile，避免过滤转发微博）
        url = f'{self.base_url}/{self.user_id}'
        params = {'page': page} if page > 1 else {}
        
        try:
            async with httpx.AsyncClient(timeout=self.config['timeout'], follow_redirects=True, verify=False) as client:
                self.client = client  # 保存client用于_fetch_all_images
                response = await client.get(url, headers=self.headers, params=params)
                
                if response.status_code == 200:
                    # 解析HTML
                    html = response.text
                    weibos = self._parse_html_page(html)
                    
                    if weibos:
                        # 处理组图：对有picall的微博，获取所有图片
                        for weibo in weibos:
                            if weibo.get('has_picall'):
                                images = await self._fetch_all_images(weibo['has_picall'])
                                weibo['images'] = images
                                # 清除标记
                                del weibo['has_picall']
                        
                        logger.info(f"成功获取第 {page} 页数据，共 {len(weibos)} 条")
                        # 构造类似API的返回格式
                        return {
                            'ok': 1,
                            'data': {
                                'cards': [{'card_type': 9, 'mblog': w} for w in weibos]
                            }
                        }
                    else:
                        logger.warning(f"第 {page} 页没有解析到微博")
                        return None
                else:
                    logger.error(f"HTTP错误: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None
    
    def _parse_html_page(self, html: str) -> List[Dict]:
        """
        解析HTML页面提取微博数据
        
        Args:
            html: HTML内容
            
        Returns:
            微博列表
        """
        soup = BeautifulSoup(html, 'lxml')
        weibos = []
        
        # 查找所有微博卡片 (weibo.cn 使用 class="c" 并且有 id 属性)
        cards = soup.find_all('div', class_='c', id=True)
        
        # 这里引入我们更稳的解析工具（避免到处复制正则/规则）
        # 兼容两种启动方式：
        # - python src/main.py（sys.path[0] == src/）
        # - python -m src.pipeline.runner（sys.path[0] == repo root）
        try:
            from pipeline.weibo_cn_parser import (  # type: ignore
                classify_retweet_from_list_card,
                detect_is_truncated,
                extract_text_html_preserve_links,
            )
        except Exception:
            from src.pipeline.weibo_cn_parser import (  # type: ignore
                classify_retweet_from_list_card,
                detect_is_truncated,
                extract_text_html_preserve_links,
            )

        for card in cards:
            try:
                # 微博ID就是div的id属性
                mid = card.get('id', '')
                if not mid or not mid.startswith('M_'):
                    continue
                
                # 提取文本内容 (span class="ctt" 包含正文)
                content = card.find('span', class_='ctt')
                text, html_with_links = extract_text_html_preserve_links(content) if content else ("", "")
                
                # 检测是否有"全文"链接（内容被折叠）
                is_truncated = detect_is_truncated(content)
                has_full_text = bool(is_truncated)  # 兼容旧字段名
                weibo_id_for_detail = mid.replace('M_', '') if is_truncated else None
                
                # 如果没有正文，跳过
                if not text:
                    # 尝试获取所有文本（可能是转发）
                    text = card.get_text().strip()
                    if not text or len(text) < 10:
                        continue
                
                # 提取时间和来源 (span class="ct" 包含时间和来源)
                time_element = card.find('span', class_='ct')
                created_at = ''
                source = ''
                
                if time_element:
                    time_text = time_element.get_text()
                    # 时间和来源用"来自"分隔
                    if '来自' in time_text:
                        parts = time_text.split('来自')
                        created_at = parts[0].strip()
                        source = parts[1].strip() if len(parts) > 1 else ''
                    else:
                        created_at = time_text.strip()
                
                # 提取互动数据 (赞、转发、评论)
                reposts_count = 0
                comments_count = 0
                attitudes_count = 0
                
                # 查找包含"赞["的文本
                action_text = card.get_text()
                import re
                if '赞[' in action_text:
                    match = re.search(r'赞\[(\d+)\]', action_text)
                    if match:
                        attitudes_count = int(match.group(1))
                if '转发[' in action_text:
                    match = re.search(r'转发\[(\d+)\]', action_text)
                    if match:
                        reposts_count = int(match.group(1))
                if '评论[' in action_text:
                    match = re.search(r'评论\[(\d+)\]', action_text)
                    if match:
                        comments_count = int(match.group(1))
                
                # 提取图片
                images = []
                image_ids = set()  # 用于去重的图片ID集合
                
                def normalize_image_url(url):
                    """统一图片URL格式，提取图片ID用于去重"""
                    if not url or 'sinaimg.cn' not in url:
                        return None, None
                    # 提取图片ID（路径的最后部分，去除扩展名）
                    parts = url.split('/')
                    if len(parts) < 2:
                        return None, None
                    pic_id = parts[-1].split('.')[0]  # 去除扩展名
                    # 确保URL带.jpg扩展名（如果原本没有）
                    if not url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        url = url + '.jpg'
                    return pic_id, url
                
                # 检查是否有多张图片（组图）
                picall_link = card.find('a', href=lambda x: x and 'picAll' in str(x))
                if picall_link:
                    # 有组图，标记需要获取
                    picall_href = picall_link.get('href', '')
                    images = []  # 先置空，后续统一获取
                    has_picall = picall_href  # 保存链接
                else:
                    has_picall = None
                    # 单图或无图，使用原来的方法
                    # 方法1: 从img标签提取（缩略图，但可以转换为大图）
                    img_tags = card.find_all('img')
                    for img in img_tags:
                        src = img.get('src', '')
                        if 'sinaimg.cn' in src and ('wap180' in src or 'thumb180' in src or 'orj360' in src):
                            # 转换为large大图
                            large_url = src.replace('/wap180/', '/large/').replace('/thumb180/', '/large/').replace('/orj360/', '/large/')
                            pic_id, normalized_url = normalize_image_url(large_url)
                            if pic_id and pic_id not in image_ids:
                                image_ids.add(pic_id)
                                images.append(normalized_url)
                    
                    # 方法2: 从原图链接提取
                    oripic_links = card.find_all('a', href=lambda x: x and 'oripic' in str(x))
                    for link in oripic_links:
                        href = link.get('href', '')
                        # 提取图片ID： oripic?id=xxx&u=图片ID
                        if '&u=' in href:
                            pic_id_raw = href.split('&u=')[-1]
                            large_url = f'https://wx1.sinaimg.cn/large/{pic_id_raw}'
                            pic_id, normalized_url = normalize_image_url(large_url)
                            if pic_id and pic_id not in image_ids:
                                image_ids.add(pic_id)
                                images.append(normalized_url)
                
                # 检测视频（只抓取原创视频）
                videos = []
                video_links = card.find_all('a', href=lambda x: x and 'video.weibo.com' in str(x))
                for video_link in video_links:
                    # 检查是否是原创（不是转发的视频）
                    # 如果是原创，会在当前卡片内找到视频链接
                    # 转发的视频通常在转发内容中
                    videos.append({
                        'url': video_link.get('href', ''),
                        'cover': ''  # 暂时为空，后续可从详情页获取
                    })
                
                # 识别是否为转发行为（快速判定：长转发需要详情页再确认）
                is_forward_action, _meta = classify_retweet_from_list_card(card)

                weibo = {
                    'id': mid,
                    'user_id': self.user_id,
                    'created_at': created_at,
                    'text': text,
                    'html_with_links': html_with_links,
                    'source': source,
                    'reposts_count': reposts_count,
                    'comments_count': comments_count,
                    'attitudes_count': attitudes_count,
                    'images': images,
                    'videos': videos,
                    'has_full_text': has_full_text,  # 标记是否需要获取完整内容
                    'weibo_id_for_detail': weibo_id_for_detail if has_full_text else None,
                    'has_picall': has_picall,  # 标记是否有组图需要获取
                    # 增量字段：可直接落库（后续 detail_enrich 可能会把 long_comment 翻转为原创）
                    'is_truncated': 1 if is_truncated else 0,
                    'detail_fetched': 0,
                    'is_retweet': 1 if is_forward_action else 0,
                    'retweet_category': 'retweet' if is_forward_action else 'original',
                    # 证据写入 raw_json（不新增列）：便于未来离线审计/纠错，不再依赖 weibo.text（ctt）是否包含“转发了”
                    'retweet_meta': _meta,
                }
                
                weibos.append(weibo)
                logger.debug(f"解析微博成功: {mid[:20]}...")
                
            except Exception as e:
                logger.debug(f"解析单条微博失败: {e}")
                continue
        
        return weibos
    
    async def _fetch_all_images(self, picall_href: str) -> List[str]:
        """
        获取组图中的所有图片
        
        Args:
            picall_href: picAll页面的链接（如：/mblog/picAll/QhBwtfPOE?rl=2）
        
        Returns:
            图片URL列表
        """
        images = []
        image_ids = set()
        
        # 构建完整URL
        if not picall_href.startswith('http'):
            picall_url = f"{self.base_url}{picall_href}"
        else:
            picall_url = picall_href
        
        try:
            await asyncio.sleep(self.request_delay)
            
            response = await self.client.get(
                picall_url,
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                logger.warning(f"获取组图失败: HTTP {response.status_code}")
                return images
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 提取所有图片
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src', '')
                if 'sinaimg.cn' in src and ('wap' in src or 'thumb' in src or 'orj' in src):
                    # 转换为large大图
                    large_url = src.replace('/wap180/', '/large/').replace('/thumb180/', '/large/').replace('/orj360/', '/large/')
                    # 提取图片ID用于去重
                    parts = large_url.split('/')
                    if len(parts) >= 2:
                        pic_id = parts[-1].split('.')[0]
                        if pic_id not in image_ids:
                            image_ids.add(pic_id)
                            # 确保URL带扩展名
                            if not large_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                large_url = large_url + '.jpg'
                            images.append(large_url)
            
            logger.debug(f"组图获取成功: {len(images)} 张图片")
            
        except Exception as e:
            logger.warning(f"获取组图异常: {e}")
        
        return images
    
    async def fetch_weibo_detail(self, weibo_id: str) -> Optional[Dict]:
        """
        获取微博详情页的完整内容和图片
        
        Args:
            weibo_id: 微博ID（不带M_前缀）
            
        Returns:
            包含 text 和 images 的字典，如果获取失败返回None
        """
        url = f'{self.base_url}/{self.user_id}/{weibo_id}'
        
        try:
            async with httpx.AsyncClient(timeout=self.config['timeout'], follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    result = {
                        'text': None,
                        'images': []
                    }
                    
                    # 1. 提取完整内容
                    content = soup.find('span', class_='ctt')
                    if content:
                        # 移除"全文"链接
                        for a in content.find_all('a'):
                            if a.get_text() == '全文':
                                a.decompose()
                        
                        result['text'] = content.get_text().strip()
                    
                    # 2. 提取图片
                    # 查找所有图片相关的链接
                    img_tags = soup.find_all('img')
                    image_ids = set()  # 用于去重
                    
                    for img in img_tags:
                        src = img.get('src', '')
                        if 'sinaimg.cn' in src and ('wap' in src or 'thumb' in src or 'orj' in src):
                            # 转换为large大图
                            large_url = src.replace('/wap180/', '/large/').replace('/thumb180/', '/large/').replace('/orj360/', '/large/')
                            
                            # 提取图片ID用于去重
                            parts = large_url.split('/')
                            if len(parts) >= 2:
                                pic_id = parts[-1].split('.')[0]
                                if pic_id not in image_ids:
                                    image_ids.add(pic_id)
                                    # 确保URL带扩展名
                                    if not large_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                        large_url = large_url + '.jpg'
                                    result['images'].append(large_url)
                    
                    # 也可以从原图链接提取
                    oripic_links = soup.find_all('a', href=lambda x: x and 'oripic' in str(x))
                    for link in oripic_links:
                        href = link.get('href', '')
                        if '&u=' in href:
                            pic_id_raw = href.split('&u=')[-1]
                            # 去除可能的参数（如 &rl=1）
                            if '&' in pic_id_raw:
                                pic_id_raw = pic_id_raw.split('&')[0]
                            pic_id = pic_id_raw.split('.')[0]
                            if pic_id not in image_ids:
                                image_ids.add(pic_id)
                                large_url = f'https://wx1.sinaimg.cn/large/{pic_id_raw}'
                                if not large_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                    large_url = large_url + '.jpg'
                                result['images'].append(large_url)
                    
                    if result['text'] or result['images']:
                        logger.debug(f"获取详情成功: {weibo_id} (文本: {len(result['text']) if result['text'] else 0}字, 图片: {len(result['images'])}张)")
                        return result
                    
                logger.warning(f"详情页未找到内容: {weibo_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取详情失败 {weibo_id}: {e}")
            return None
    
    async def fetch_all_weibos(self, start_page: int = 1) -> List[Dict[str, Any]]:
        """
        获取所有微博数据
        
        Args:
            start_page: 起始页码（支持断点续传）
            
        Returns:
            微博列表
        """
        all_weibos = []
        page = start_page
        retry_count = 0
        max_retries = self.config.get('retry_times', 3)
        
        logger.info(f"开始抓取微博，从第 {start_page} 页开始")
        
        while True:
            # 请求延迟
            if page > start_page:
                delay = self.config.get('request_delay', 1.0)
                await asyncio.sleep(delay)
            
            data = await self.fetch_user_weibos(page)
            
            if data is None:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"第 {page} 页重试 {max_retries} 次后仍失败，停止抓取")
                    break
                logger.warning(f"第 {page} 页失败，重试 {retry_count}/{max_retries}")
                await asyncio.sleep(2)
                continue
            
            # 重置重试计数
            retry_count = 0
            
            # 解析微博数据
            cards = data.get('data', {}).get('cards', [])
            if not cards:
                logger.info(f"第 {page} 页没有更多数据，抓取完成")
                break
            
            # 提取微博内容
            page_weibos = []
            for card in cards:
                if card.get('card_type') == 9:  # 普通微博
                    mblog = card.get('mblog')
                    if mblog:
                        weibo = self._parse_weibo(mblog)
                        if weibo:
                            page_weibos.append(weibo)
            
            if not page_weibos:
                logger.info(f"第 {page} 页没有有效微博，可能到达末尾")
                break
            
            all_weibos.extend(page_weibos)
            logger.info(f"第 {page} 页获取 {len(page_weibos)} 条微博，累计 {len(all_weibos)} 条")
            
            page += 1
        
        # 处理需要获取完整内容的微博
        weibos_need_detail = [w for w in all_weibos if w.get('has_full_text')]
        if weibos_need_detail:
            logger.info(f"发现 {len(weibos_need_detail)} 条微博需要获取完整内容...")
            for weibo in weibos_need_detail:
                weibo_id = weibo.get('weibo_id_for_detail')
                if weibo_id:
                    full_text = await self.fetch_weibo_detail(weibo_id)
                    if full_text:
                        weibo['text'] = full_text
                    await asyncio.sleep(0.5)  # 避免请求过快
        
        logger.info(f"微博抓取完成，共 {len(all_weibos)} 条")
        return all_weibos
    
    def _parse_weibo(self, mblog: Dict) -> Optional[Dict[str, Any]]:
        """
        解析单条微博数据
        
        Args:
            mblog: 微博原始数据
            
        Returns:
            解析后的微博数据
        """
        try:
            weibo = {
                'id': str(mblog.get('id', '')),
                'user_id': str(mblog.get('user', {}).get('id', self.user_id)),
                'created_at': self._parse_time(mblog.get('created_at', '')),
                'text': self._clean_text(mblog.get('text', '')),
                'source': mblog.get('source', ''),
                'reposts_count': mblog.get('reposts_count', 0),
                'comments_count': mblog.get('comments_count', 0),
                'attitudes_count': mblog.get('attitudes_count', 0),
                'images': [],
                'videos': [],
            }
            
            # 提取图片
            pics = mblog.get('pics', [])
            for pic in pics:
                large_url = pic.get('large', {}).get('url')
                if large_url:
                    weibo['images'].append(large_url)
            
            # 提取视频
            page_info = mblog.get('page_info')
            if page_info and page_info.get('type') == 'video':
                media_info = page_info.get('media_info')
                if media_info:
                    video_url = media_info.get('stream_url_hd') or media_info.get('stream_url')
                    if video_url:
                        weibo['videos'].append({
                            'url': video_url,
                            'cover': page_info.get('page_pic', '')
                        })
            
            # 处理转发微博
            retweeted = mblog.get('retweeted_status')
            if retweeted:
                weibo['retweeted'] = self._parse_weibo(retweeted)
            
            return weibo
            
        except Exception as e:
            logger.error(f"解析微博失败: {e}")
            return None
    
    def _clean_text(self, html_text: str) -> str:
        """
        清理HTML文本，保留纯文本内容
        
        Args:
            html_text: HTML格式的文本
            
        Returns:
            纯文本
        """
        if not html_text:
            return ''
        
        # 使用BeautifulSoup解析
        soup = BeautifulSoup(html_text, 'lxml')
        
        # 移除所有的a标签但保留文本
        for a in soup.find_all('a'):
            a.replace_with(a.get_text())
        
        text = soup.get_text()
        
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        """
        解析微博时间字符串
        
        Args:
            time_str: 时间字符串（如："刚刚"、"5分钟前"、"今天 12:30"、"2023-01-01"）
            
        Returns:
            标准格式时间字符串
        """
        if not time_str:
            return None
        
        try:
            # 尝试解析标准格式
            if re.match(r'\d{4}-\d{2}-\d{2}', time_str):
                return time_str
            
            # TODO: 可以添加更复杂的时间解析逻辑
            # 暂时返回原始字符串
            return time_str
            
        except Exception as e:
            logger.warning(f"时间解析失败: {time_str}, {e}")
            return time_str
    
    async def test_connection(self) -> bool:
        """
        测试连接是否有效
        
        Returns:
            连接是否成功
        """
        logger.info("测试微博连接...")
        data = await self.fetch_user_weibos(page=1)
        
        if data:
            logger.info("✓ 连接测试成功！Cookie有效")
            return True
        else:
            logger.error("✗ 连接测试失败！请检查Cookie是否有效")
            return False

