"""
HTML生成模块 - 生成Apple风格的微博备份页面
"""
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
import json


class HTMLGenerator:
    """HTML生成器"""
    
    def __init__(self, config: Dict, template_dir: str = 'templates'):
        """
        初始化生成器
        
        Args:
            config: 配置信息
            template_dir: 模板目录
        """
        self.config = config
        self.template_dir = Path(template_dir)
        self.output_dir = Path(config['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"HTMLGenerator 初始化完成")
    
    def generate(self, weibos: List[Dict], images_map: Dict, videos_map: Dict,
                 stats: Dict) -> str:
        """
        生成HTML文件
        
        Args:
            weibos: 微博列表
            images_map: 图片映射 {weibo_id: [images]}
            videos_map: 视频映射 {weibo_id: [videos]}
            stats: 统计信息
            
        Returns:
            生成的HTML文件路径
        """
        logger.info("开始生成HTML...")
        
        # 处理时间格式，识别2025年的微博
        weibos = self._process_weibo_dates(weibos)
        
        # 按时间排序：2025年的在前，然后是其他的
        weibos_sorted = self._sort_weibos_by_date(weibos)
        
        # 读取模板
        template = self._get_template()
        
        # 生成微博HTML
        weibos_html = self._generate_weibos_html(weibos_sorted, images_map, videos_map)
        
        # 生成统计信息HTML
        stats_html = self._generate_stats_html(stats, weibos_sorted)
        
        # 替换模板内容
        html = template.replace('{{STATS}}', stats_html)
        html = html.replace('{{WEIBOS}}', weibos_html)
        html = html.replace('{{TOTAL_COUNT}}', str(len(weibos_sorted)))
        
        # 保存文件
        output_file = self.output_dir / 'index.html'
        output_file.write_text(html, encoding='utf-8')
        
        logger.info(f"✓ HTML生成完成: {output_file}")
        return str(output_file)
    
    def _process_weibo_dates(self, weibos: List[Dict]) -> List[Dict]:
        """
        处理微博时间，标记2025年的微博
        
        Args:
            weibos: 微博列表
            
        Returns:
            处理后的微博列表
        """
        import re
        
        for weibo in weibos:
            created_at = weibo.get('created_at', '')
            
            # 检查是否是"XX月XX日"格式（没有年份）
            if created_at and re.match(r'^\d{1,2}月\d{1,2}日', created_at):
                # 加上2025年
                weibo['created_at'] = f"2025年{created_at}"
                weibo['is_2025'] = True
                logger.debug(f"补充年份: {created_at} -> {weibo['created_at']}")
            # 检查是否已经是2025年的微博
            elif created_at and created_at.startswith('2025'):
                weibo['is_2025'] = True
            else:
                weibo['is_2025'] = False
        
        return weibos
    
    def _sort_weibos_by_date(self, weibos: List[Dict]) -> List[Dict]:
        """
        对微博按时间排序，2025年的放在最前面，并按时间倒序
        
        Args:
            weibos: 微博列表
            
        Returns:
            排序后的微博列表
        """
        from datetime import datetime
        import re
        
        def parse_date_for_sort(created_at: str):
            """解析日期用于排序，返回可比较的元组"""
            if not created_at:
                return (0, 0, 0, 0, 0)  # 无日期的排最后
            
            # 尝试解析 "2025年12月06日 10:59" 格式
            match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{1,2})', created_at)
            if match:
                year, month, day, hour, minute = match.groups()
                return (int(year), int(month), int(day), int(hour), int(minute))
            
            # 尝试解析 "2024-12-31 16:43:44" 格式
            match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', created_at)
            if match:
                year, month, day, hour, minute = match.groups()
                return (int(year), int(month), int(day), int(hour), int(minute))
            
            # 默认返回最小值
            return (0, 0, 0, 0, 0)
        
        # 分离2025年和其他年份的微博
        weibos_2025 = [w for w in weibos if w.get('is_2025', False)]
        weibos_other = [w for w in weibos if not w.get('is_2025', False)]
        
        # 对2025年的微博按时间倒序排列（最新的在前）
        weibos_2025_sorted = sorted(
            weibos_2025, 
            key=lambda w: parse_date_for_sort(w.get('created_at', '')),
            reverse=True
        )
        
        # 对其他年份的微博也按时间倒序排列
        weibos_other_sorted = sorted(
            weibos_other,
            key=lambda w: parse_date_for_sort(w.get('created_at', '')),
            reverse=True
        )
        
        logger.info(f"2025年微博: {len(weibos_2025_sorted)} 条（已按时间倒序）")
        logger.info(f"其他年份微博: {len(weibos_other_sorted)} 条（已按时间倒序）")
        
        # 2025年的在前，其他的在后
        return weibos_2025_sorted + weibos_other_sorted
    
    def _get_template(self) -> str:
        """获取HTML模板"""
        template_file = self.template_dir / 'index.html'
        
        if template_file.exists():
            return template_file.read_text(encoding='utf-8')
        else:
            # 使用内置模板
            return self._get_builtin_template()
    
    def _generate_weibos_html(self, weibos: List[Dict], images_map: Dict, 
                              videos_map: Dict) -> str:
        """生成微博列表HTML"""
        html_parts = []
        
        for weibo in weibos:
            weibo_id = weibo['id']
            
            # 解析raw_json
            try:
                raw_data = json.loads(weibo['raw_json'])
            except:
                raw_data = {}
            
            # 获取关联的图片和视频
            images = images_map.get(weibo_id, [])
            videos = videos_map.get(weibo_id, [])
            
            # 获取转发标记（默认为0，即原创）
            is_retweet = weibo.get('is_retweet', 0)
            tag_text = "转发" if str(is_retweet) == "1" else "原创"
            tag_class = "weibo-tag-retweet" if str(is_retweet) == "1" else "weibo-tag-original"
            
            # 生成单条微博HTML
            # 优先使用带链接的HTML内容（存放在 raw_json 里，DB列可能不存在）
            html_with_links = raw_data.get('html_with_links') or weibo.get('html_with_links')
            if html_with_links:
                # 已有链接信息，直接使用
                formatted_content = html_with_links.replace('\n', '<br>')
            else:
                # 降级到纯文本格式
                formatted_content = self._format_text(weibo.get('text', ''))
            
            weibo_html = f'''
            <div class="weibo-card" data-id="{weibo_id}" data-is-retweet="{is_retweet}">
                <div class="weibo-header">
                    <div class="weibo-time">
                        <span class="weibo-tag {tag_class}">{tag_text}</span>
                        <span class="weibo-time-text">{weibo.get('created_at', '')}</span>
                    </div>
                    <div class="weibo-source">{weibo.get('source', '')}</div>
                </div>
                <div class="weibo-content">
                    <p>{formatted_content}</p>
                </div>
            '''
            
            # 添加图片
            if images:
                weibo_html += '<div class="weibo-images">'
                for img in images:
                    if img.get('local_path'):
                        weibo_html += f'<img src="../{img["local_path"]}" alt="图片" loading="lazy" onclick="openLightbox(this.src)">'
                weibo_html += '</div>'
            
            # 添加视频
            if videos:
                weibo_html += '<div class="weibo-videos">'
                for vid in videos:
                    if vid.get('local_path'):
                        weibo_html += f'''
                        <video controls preload="metadata">
                            <source src="../{vid['local_path']}" type="video/mp4">
                        </video>
                        '''
                weibo_html += '</div>'
            
            # 添加互动数据
            weibo_html += f'''
                <div class="weibo-stats">
                    <span>转发 {weibo.get('reposts_count', 0)}</span>
                    <span>评论 {weibo.get('comments_count', 0)}</span>
                    <span>点赞 {weibo.get('attitudes_count', 0)}</span>
                </div>
            </div>
            '''
            
            html_parts.append(weibo_html)
        
        return '\n'.join(html_parts)
    
    def _generate_stats_html(self, stats: Dict, weibos: List[Dict]) -> str:
        """生成统计信息HTML（动态计算）"""
        # 动态计算实际数量（确保准确）
        actual_weibo_count = len(weibos)
        
        # 计算实际图片数
        actual_image_count = 0
        actual_video_count = 0
        for weibo in weibos:
            # 这里假设weibo对象中有image_count和video_count字段
            # 如果没有，我们使用stats中的总数
            pass
        
        # 从stats中获取总数（数据库统计）
        total_images = stats.get('total_images', 0)
        total_videos = stats.get('total_videos', 0)
        downloaded_images = stats.get('downloaded_images', 0)
        downloaded_videos = stats.get('downloaded_videos', 0)
        
        # 计算总互动数（动态）
        total_reposts = sum(w.get('reposts_count', 0) for w in weibos)
        total_comments = sum(w.get('comments_count', 0) for w in weibos)
        total_likes = sum(w.get('attitudes_count', 0) for w in weibos)
        total_interactions = total_reposts + total_comments + total_likes
        
        # 计算年份范围
        years = set()
        for weibo in weibos:
            created_at = weibo.get('created_at', '')
            if created_at:
                # 提取年份
                if created_at.startswith('20'):
                    year = created_at[:4]
                    years.add(year)
        
        year_range = f"{min(years) if years else '?'} - {max(years) if years else '?'}"
        year_count = len(years)
        
        # 计算平均每日发布数
        if years and len(years) > 0:
            days_span = (int(max(years)) - int(min(years)) + 1) * 365
            avg_per_day = actual_weibo_count / days_span if days_span > 0 else 0
        else:
            avg_per_day = 0
        
        # 格式化大数字
        def format_number(n):
            if n >= 10000:
                return f"{n/10000:.1f}万"
            elif n >= 1000:
                return f"{n/1000:.1f}k"
            else:
                return str(n)
        
        html = f'''
        <div class="stat-item">
            <div class="stat-value">{actual_weibo_count}</div>
            <div class="stat-label">微博总数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{total_images}</div>
            <div class="stat-label">图片（{downloaded_images}已下载）</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{format_number(total_interactions)}</div>
            <div class="stat-label">总互动</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{year_count}年</div>
            <div class="stat-label">时间跨度（{year_range}）</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{format_number(total_likes)}</div>
            <div class="stat-label">获赞</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{format_number(total_comments)}</div>
            <div class="stat-label">评论</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{format_number(total_reposts)}</div>
            <div class="stat-label">转发</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{avg_per_day:.1f}</div>
            <div class="stat-label">日均发布</div>
        </div>
        '''
        
        return html
    
    def _format_text(self, text: str) -> str:
        """格式化文本（转义HTML，保留换行）"""
        if not text:
            return ''
        
        # HTML转义
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        
        # 换行转为<br>
        text = text.replace('\n', '<br>')
        
        return text
    
    def _get_builtin_template(self) -> str:
        """获取内置HTML模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微博备份</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            line-height: 1.6;
        }
        
        .container {
            max-width: 980px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        header {
            text-align: center;
            margin-bottom: 60px;
        }
        
        h1 {
            font-size: 48px;
            font-weight: 600;
            letter-spacing: -0.02em;
            margin-bottom: 12px;
        }
        
        .subtitle {
            font-size: 21px;
            color: #6e6e73;
            font-weight: 400;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 60px;
        }
        
        .stat-item {
            background: white;
            padding: 30px;
            border-radius: 18px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        .stat-value {
            font-size: clamp(20px, 3vw, 32px);
            font-weight: 600;
            color: #0066cc;
            margin-bottom: 8px;
            word-break: break-all;
            line-height: 1.2;
        }
        
        .stat-label {
            font-size: 17px;
            color: #6e6e73;
        }
        
        .weibo-list {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        
        .weibo-card {
            background: white;
            border-radius: 18px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }
        
        .weibo-card:hover {
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }
        
        .weibo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #e5e5e7;
        }
        
        .weibo-time {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 15px;
            color: #6e6e73;
        }

        .weibo-tag {
            display: inline-flex;
            align-items: center;
            font-size: 12px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 999px;
            border: 1px solid rgba(0,0,0,0.08);
            background: rgba(0,0,0,0.03);
            color: #1d1d1f;
            line-height: 1.6;
            flex: 0 0 auto;
        }

        .weibo-tag-original {
            background: rgba(52, 199, 89, 0.10);
            border-color: rgba(52, 199, 89, 0.25);
            color: #0a7a2a;
        }

        .weibo-tag-retweet {
            background: rgba(255, 149, 0, 0.12);
            border-color: rgba(255, 149, 0, 0.28);
            color: #b35a00;
        }
        
        .weibo-source {
            font-size: 13px;
            color: #86868b;
        }
        
        .weibo-content {
            margin-bottom: 20px;
        }
        
        .weibo-content p {
            font-size: 15px;
            line-height: 1.7;
            color: #1d1d1f;
        }
        
        .weibo-images {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        
        .weibo-images img {
            width: 100%;
            height: auto;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        
        .weibo-images img:hover {
            transform: scale(1.02);
        }
        
        .weibo-videos {
            margin-bottom: 20px;
        }
        
        .weibo-videos video {
            width: 100%;
            max-width: 600px;
            border-radius: 12px;
            outline: none;
        }
        
        .weibo-stats {
            display: flex;
            gap: 24px;
            font-size: 15px;
            color: #6e6e73;
        }
        
        .weibo-stats span {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        /* 微博内容中的链接样式 */
        .weibo-content a {
            color: #0066cc;
            text-decoration: none;
            transition: all 0.2s ease;
        }
        
        .weibo-content a:hover {
            color: #004499;
            text-decoration: underline;
        }
        
        .weibo-content a.mention {
            color: #0066cc;
            font-weight: 500;
        }
        
        .weibo-content a.topic {
            color: #0066cc;
            font-weight: 500;
        }
        
        .weibo-content a.link {
            color: #0066cc;
        }
        
        footer {
            text-align: center;
            margin-top: 80px;
            padding-top: 40px;
            border-top: 1px solid #e5e5e7;
            color: #6e6e73;
            font-size: 15px;
        }
        
        /* 筛选器样式 */
        .filter-container {
            background: white;
            border-radius: 18px;
            padding: 24px 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }
        
        .filter-label {
            font-size: 17px;
            font-weight: 500;
            color: #1d1d1f;
        }
        
        .filter-container select {
            background: #f5f5f7;
            border: 1px solid #e5e5e7;
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 15px;
            color: #1d1d1f;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
            outline: none;
            min-width: 140px;
        }
        
        .filter-container select:hover {
            background: #ebebed;
            border-color: #0066cc;
        }
        
        .filter-container select:focus {
            background: white;
            border-color: #0066cc;
            box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
        }
        
        .filter-result {
            font-size: 15px;
            color: #6e6e73;
            margin-left: auto;
        }
        
        .filter-result .count {
            color: #0066cc;
            font-weight: 600;
            font-size: 17px;
        }
        
        /* Apple风格开关样式 */
        .filter-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            user-select: none;
        }
        
        .filter-toggle input[type="checkbox"] {
            display: none;
        }
        
        .toggle-switch {
            position: relative;
            width: 51px;
            height: 31px;
            background: #e5e5e7;
            border-radius: 31px;
            transition: background-color 0.3s ease;
            cursor: pointer;
        }
        
        .toggle-switch::after {
            content: '';
            position: absolute;
            top: 2px;
            left: 2px;
            width: 27px;
            height: 27px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .filter-toggle input[type="checkbox"]:checked + .toggle-switch {
            background: #34c759;
        }
        
        .filter-toggle input[type="checkbox"]:checked + .toggle-switch::after {
            transform: translateX(20px);
        }
        
        .toggle-label {
            font-size: 15px;
            color: #1d1d1f;
            font-weight: 400;
        }
        
        /* 分页样式 */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 40px 0;
            flex-wrap: wrap;
        }
        
        .pagination button {
            background: white;
            border: 1px solid #e5e5e7;
            border-radius: 8px;
            padding: 10px 16px;
            font-size: 15px;
            color: #1d1d1f;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        
        .pagination button:hover:not(:disabled) {
            background: #f5f5f7;
            border-color: #0066cc;
            color: #0066cc;
        }
        
        .pagination button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .pagination button.active {
            background: #0066cc;
            color: white;
            border-color: #0066cc;
        }
        
        .pagination .page-info {
            font-size: 15px;
            color: #6e6e73;
            padding: 0 10px;
        }
        
        @media (max-width: 768px) {
            h1 {
                font-size: 32px;
            }
            
            .subtitle {
                font-size: 17px;
            }
            
            .weibo-card {
                padding: 20px;
            }
            
            .weibo-images {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }
            
            .pagination {
                gap: 5px;
            }
            
            .pagination button {
                padding: 8px 12px;
                font-size: 14px;
            }
            
            .filter-container {
                padding: 20px;
                gap: 12px;
            }
            
            .filter-container select {
                min-width: 120px;
                font-size: 14px;
            }
            
            .filter-result {
                width: 100%;
                text-align: center;
                margin-left: 0;
                margin-top: 8px;
            }
            
            .filter-toggle {
                width: 100%;
                justify-content: center;
            }
        }
        
        /* Lightbox 样式 */
        .lightbox {
            display: none;
            position: fixed;
            z-index: 9999;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.95);
            justify-content: center;
            align-items: center;
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .lightbox-content {
            max-width: 90%;
            max-height: 90vh;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
            cursor: default;
            animation: zoomIn 0.3s;
        }
        
        @keyframes zoomIn {
            from {
                transform: scale(0.8);
                opacity: 0;
            }
            to {
                transform: scale(1);
                opacity: 1;
            }
        }
        
        .lightbox-close {
            position: absolute;
            top: 20px;
            right: 40px;
            color: #fff;
            font-size: 50px;
            font-weight: 300;
            cursor: pointer;
            transition: color 0.3s;
            user-select: none;
            line-height: 1;
        }
        
        .lightbox-close:hover {
            color: #bbb;
        }
        
        .weibo-images img {
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .weibo-images img:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
    </style>
    <script>
        const ITEMS_PER_PAGE = 300;
        let currentPage = 1;
        let totalPages = 1;
        let allItems = [];
        let filteredItems = [];
        let currentYearFilter = 'all';
        let currentMonthFilter = 'all';
        let showOriginalOnly = false;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            allItems = Array.from(document.querySelectorAll('.weibo-card'));
            filteredItems = allItems;
            
            // 提取所有年月数据并填充下拉框
            initializeFilters();
            
            // 显示第一页
            applyFilter();
        });
        
        // 初始化筛选器
        function initializeFilters() {
            const yearMonthSet = new Set();
            const yearSet = new Set();
            const monthSet = new Set();
            
            allItems.forEach(item => {
                const timeEl = item.querySelector('.weibo-time-text') || item.querySelector('.weibo-time');
                const timeText = timeEl ? timeEl.textContent.trim() : '';
                
                // 支持两种格式：
                // 1. "2025年12月10日 18:11" 或 "12月10日 18:11" (2025年)
                // 2. "2024-12-31 16:43:44" (完整时间戳)
                
                let year = null;
                let month = null;
                
                // 格式1: YYYY年MM月 或 MM月（2025年）
                const match1 = timeText.match(/(\d{4})年(\d{1,2})月/);
                if (match1) {
                    year = match1[1];
                    month = parseInt(match1[2]);
                } else {
                    // 2025年格式（无年份）
                    const match2 = timeText.match(/^(\d{1,2})月/);
                    if (match2) {
                        year = '2025';
                        month = parseInt(match2[1]);
                    } else {
                        // 格式2: YYYY-MM-DD HH:MM:SS
                        const match3 = timeText.match(/^(\d{4})-(\d{2})-/);
                        if (match3) {
                            year = match3[1];
                            month = parseInt(match3[2]);
                        }
                    }
                }
                
                if (year && month) {
                    yearSet.add(year);
                    monthSet.add(month);
                    yearMonthSet.add(`${year}-${month}`);
                }
            });
            
            // 填充年份下拉框（从新到旧）
            const yearSelect = document.getElementById('yearFilter');
            const years = Array.from(yearSet).sort((a, b) => b - a);
            years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year + '年';
                yearSelect.appendChild(option);
            });
            
            // 填充月份下拉框（从12到1）
            const monthSelect = document.getElementById('monthFilter');
            const months = Array.from(monthSet).sort((a, b) => b - a);
            months.forEach(month => {
                const option = document.createElement('option');
                option.value = month;
                option.textContent = month + '月';
                monthSelect.appendChild(option);
            });
        }
        
        // 应用筛选
        function applyFilter() {
            currentYearFilter = document.getElementById('yearFilter').value;
            currentMonthFilter = document.getElementById('monthFilter').value;
            showOriginalOnly = document.getElementById('originalOnlyFilter').checked;
            
            // 筛选微博
            filteredItems = allItems.filter(item => {
                const timeEl = item.querySelector('.weibo-time-text') || item.querySelector('.weibo-time');
                const timeText = timeEl ? timeEl.textContent.trim() : '';
                
                let year = null;
                let month = null;
                
                // 支持两种格式：
                // 1. "2025年12月10日 18:11" 或 "12月10日 18:11"
                const match1 = timeText.match(/(\d{4})年(\d{1,2})月/);
                if (match1) {
                    year = match1[1];
                    month = parseInt(match1[2]);
                } else {
                    // 2025年格式（无年份）
                    const match2 = timeText.match(/^(\d{1,2})月/);
                    if (match2) {
                        year = '2025';
                        month = parseInt(match2[1]);
                    } else {
                        // 2. "2024-12-31 16:43:44"
                        const match3 = timeText.match(/^(\d{4})-(\d{2})-/);
                        if (match3) {
                            year = match3[1];
                            month = parseInt(match3[2]);
                        }
                    }
                }
                
                if (!year || !month) return false;
                
                // 年份筛选
                if (currentYearFilter !== 'all' && year !== currentYearFilter) {
                    return false;
                }
                
                // 月份筛选
                if (currentMonthFilter !== 'all' && month !== parseInt(currentMonthFilter)) {
                    return false;
                }
                
                // 原创内容筛选
                if (showOriginalOnly) {
                    const isRetweet = item.getAttribute('data-is-retweet');
                    if (isRetweet === '1') {
                        return false;
                    }
                }
                
                return true;
            });
            
            // 更新结果计数
            document.getElementById('filterCount').textContent = filteredItems.length;
            
            // 重新计算分页，至少为1页
            totalPages = filteredItems.length > 0 ? Math.ceil(filteredItems.length / ITEMS_PER_PAGE) : 1;
            currentPage = 1;
            
            // 显示第一页
            showPage(1);
        }
        
        function showPage(page) {
            const start = (page - 1) * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            
            // 隐藏所有微博
            allItems.forEach(item => {
                item.style.display = 'none';
            });
            
            // 只显示筛选后的当前页微博
            filteredItems.forEach((item, index) => {
                if (index >= start && index < end) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
            
            currentPage = page;
            updatePagination();
            
            // 滚动到顶部
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        
        function updatePagination() {
            // 确保分页数据的正确性
            const displayTotalPages = Math.max(1, totalPages);
            const displayCurrentPage = filteredItems.length > 0 ? currentPage : 1;
            
            // 更新当前页显示（顶部和底部）
            document.getElementById('currentPage').textContent = displayCurrentPage;
            document.getElementById('currentPage2').textContent = displayCurrentPage;
            document.getElementById('totalPages').textContent = displayTotalPages;
            document.getElementById('totalPages2').textContent = displayTotalPages;
            
            // 更新按钮状态（顶部和底部）
            const isFirstPage = displayCurrentPage === 1 || filteredItems.length === 0;
            const isLastPage = displayCurrentPage === displayTotalPages || filteredItems.length === 0;
            
            document.getElementById('prevBtn').disabled = isFirstPage;
            document.getElementById('prevBtn2').disabled = isFirstPage;
            document.getElementById('nextBtn').disabled = isLastPage;
            document.getElementById('nextBtn2').disabled = isLastPage;
            
            // 更新页码按钮（顶部和底部）
            updatePageButtons('pageButtons');
            updatePageButtons('pageButtons2');
        }
        
        function updatePageButtons(containerId) {
            const pageButtons = document.getElementById(containerId);
            pageButtons.innerHTML = '';
            
            // 如果没有数据，不显示页码按钮
            if (filteredItems.length === 0) {
                return;
            }
            
            const displayTotalPages = Math.max(1, totalPages);
            
            // 显示当前页附近的页码
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(displayTotalPages, currentPage + 2);
            
            if (startPage > 1) {
                addPageButton(containerId, 1);
                if (startPage > 2) {
                    const span = document.createElement('span');
                    span.className = 'page-info';
                    span.textContent = '...';
                    pageButtons.appendChild(span);
                }
            }
            
            for (let i = startPage; i <= endPage; i++) {
                addPageButton(containerId, i);
            }
            
            if (endPage < displayTotalPages) {
                if (endPage < displayTotalPages - 1) {
                    const span = document.createElement('span');
                    span.className = 'page-info';
                    span.textContent = '...';
                    pageButtons.appendChild(span);
                }
                addPageButton(containerId, displayTotalPages);
            }
        }
        
        function addPageButton(containerId, page) {
            const button = document.createElement('button');
            button.textContent = page;
            button.className = page === currentPage ? 'active' : '';
            button.onclick = () => showPage(page);
            document.getElementById(containerId).appendChild(button);
        }
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>我的微博备份</h1>
            <p class="subtitle">珍藏每一刻记忆</p>
        </header>
        
        <div class="stats">
            {{STATS}}
        </div>
        
        <div class="filter-container">
            <span class="filter-label">筛选:</span>
            <select id="yearFilter" onchange="applyFilter()">
                <option value="all">全部年份</option>
            </select>
            <select id="monthFilter" onchange="applyFilter()">
                <option value="all">全部月份</option>
            </select>
            <label class="filter-toggle">
                <input type="checkbox" id="originalOnlyFilter" onchange="applyFilter()">
                <div class="toggle-switch"></div>
                <span class="toggle-label">只看原创</span>
            </label>
            <div class="filter-result">
                共找到 <span class="count" id="filterCount">0</span> 条微博
            </div>
        </div>
        
        <div class="pagination">
            <button id="prevBtn" onclick="showPage(currentPage - 1)">上一页</button>
            <div id="pageButtons"></div>
            <button id="nextBtn" onclick="showPage(currentPage + 1)">下一页</button>
            <span class="page-info">第 <span id="currentPage">1</span> / <span id="totalPages">1</span> 页</span>
        </div>
        
        <div class="weibo-list">
            {{WEIBOS}}
        </div>
        
        <div class="pagination">
            <button id="prevBtn2" onclick="showPage(currentPage - 1)">上一页</button>
            <div id="pageButtons2"></div>
            <button id="nextBtn2" onclick="showPage(currentPage + 1)">下一页</button>
            <span class="page-info">第 <span id="currentPage2">1</span> / <span id="totalPages2">1</span> 页</span>
        </div>
        
        <footer>
            <p>备份时间：''' + datetime.now().strftime('%Y年%m月%d日') + '''</p>
            <p>共 {{TOTAL_COUNT}} 条微博</p>
        </footer>
    </div>
    
    <!-- Lightbox 浮层 -->
    <div id="lightbox" class="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" class="lightbox-content" onclick="event.stopPropagation()">
        <div class="lightbox-caption"></div>
    </div>
    
    <script>
        function openLightbox(src) {
            document.getElementById('lightbox').style.display = 'flex';
            document.getElementById('lightbox-img').src = src;
            document.body.style.overflow = 'hidden';
        }
        
        function closeLightbox() {
            document.getElementById('lightbox').style.display = 'none';
            document.body.style.overflow = 'auto';
        }
        
        // ESC键关闭
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeLightbox();
            }
        });
    </script>
</body>
</html>'''

