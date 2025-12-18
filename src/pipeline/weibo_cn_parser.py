from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup


_RE_FORWARD = re.compile(r"转发了\s*@(\S+)\s*的微博")
_RE_FORWARD_REASON = re.compile(r"转发理由[:：]\s*(.*?)(?=(原文:|原文转发|原文评论|$))", re.DOTALL)
_RE_UI_TAIL = re.compile(r"(举报|收藏|操作)\s*$")
_RE_DATE_TAIL = re.compile(r"(\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})\s+\d{1,2}:\d{2}.*$")


def _clean_text(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("全文", "").strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _trim_tail_noise(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = _RE_DATE_TAIL.sub("", s).strip()
    for kw in ("举报", "收藏", "操作"):
        if kw in s:
            s = s.split(kw, 1)[0].strip()
    s = _RE_UI_TAIL.sub("", s).strip()
    return s


def detect_is_truncated(content_span: Optional[BeautifulSoup]) -> bool:
    if not content_span:
        return False
    full_text_link = content_span.find("a", string="全文")
    return full_text_link is not None


def extract_forward_reason_from_detail(card: BeautifulSoup) -> Tuple[str, int, str]:
    """
    仅在详情页明确出现“转发理由:”时提取，避免把原文算作自写评论。
    Returns (text, length, source)
    """
    if card is None:
        return "", 0, "none"
    card_text = card.get_text("\n", strip=True) or ""
    if "转发理由:" not in card_text and "转发理由：" not in card_text:
        return "", 0, "none"
    m = _RE_FORWARD_REASON.search(card_text)
    if not m:
        return "", 0, "none"
    s = _clean_text(m.group(1))
    s = _trim_tail_noise(s)
    return s, len(s), "marker_regex"


def classify_retweet_from_list_card(card: BeautifulSoup) -> Tuple[bool, Dict]:
    """
    基于列表卡片做“转发行为”识别（快速、可离线跑）。
    注意：长评论判定不可靠，真正 long_comment 在详情页确认。
    Returns (is_forward_action, meta)
    """
    card_text = card.get_text(" ", strip=True)
    content_spans = card.find_all("span", class_="ctt")
    # 主页列表里，“转发了 … 的微博”经常出现在 span.cmt（不在正文 span.ctt）
    cmt = card.find("span", class_="cmt")
    cmt_text = cmt.get_text(" ", strip=True) if cmt else ""

    has_forward_phrase = (
        ("转发了" in card_text)
        or (" 转发了 @" in card_text)
        or ("转发了" in cmt_text)
    )
    has_reason_marker = ("转发理由:" in card_text) or ("转发理由：" in card_text)
    has_original_forward_marker = ("原文转发" in card_text) or ("原文评论" in card_text)
    has_original_marker = ("原文:" in card_text) or (card_text.strip() == "转发微博")
    is_forward_action = (
        has_forward_phrase
        or has_reason_marker
        or has_original_forward_marker
        or has_original_marker
        or (len(content_spans) >= 2)
    )

    retweeted_author = ""
    m = _RE_FORWARD.search(card_text)
    if m:
        retweeted_author = f"@{m.group(1)}"

    retweet_reason = ""
    if has_reason_marker:
        m2 = re.search(r"转发理由[:：]\s*(.+)$", card_text)
        if m2:
            retweet_reason = (m2.group(1) or "").strip()

    return is_forward_action, {
        "is_forward_action": is_forward_action,
        "has_forward_phrase": has_forward_phrase,
        "has_reason_marker": has_reason_marker,
        "has_original_forward_marker": has_original_forward_marker,
        "retweeted_author": retweeted_author,
        "retweet_reason": retweet_reason,
        "cmt_text": cmt_text,
    }


def extract_text_html_preserve_links(content_span: BeautifulSoup) -> Tuple[str, str]:
    """
    从 span.ctt 中提取：
    - text: 纯文本
    - html: 保留 <a href> 的HTML（后续用于 HTML 备份页面）
    """
    if not content_span:
        return "", ""

    # 去除“全文”链接（但保留其他链接）
    span = BeautifulSoup(str(content_span), "lxml").find("span", class_="ctt") or content_span
    for a in span.find_all("a"):
        if (a.get_text() or "").strip() == "全文":
            a.decompose()

    # HTML：把 a 标签保留并加上 target
    for a in span.find_all("a"):
        href = a.get("href")
        if href:
            a["href"] = href
            a["target"] = "_blank"
            a["rel"] = "noreferrer"

    html = span.decode_contents().strip()
    text = span.get_text("\n", strip=True)
    
    # 移除开头的冒号（微博cn有时会在转发评论前加":"）
    if html.startswith(":"):
        html = html[1:].lstrip()
    if text.startswith(":"):
        text = text[1:].lstrip()
    
    return text, html


def extract_images_from_soup(soup: BeautifulSoup) -> List[str]:
    """
    从 weibo.cn 页面提取“微博正文图片”的 URL（统一为 large，去重）
    注意：
    - 页面里可能混入表情/按钮/站点静态资源（例如 h5.sinaimg.cn 的 emoticon/donate 按钮）
    - 这里明确只保留“large 图床”的图片，避免把 UI 资源写入 images 表造成大量无效下载
    """
    images: List[str] = []
    image_ids = set()

    def add_url(u: str):
        if not u or "sinaimg.cn" not in u:
            return
        large_url = (
            u.replace("/wap180/", "/large/")
            .replace("/thumb180/", "/large/")
            .replace("/orj360/", "/large/")
        )
        # 只保留“large”图床资源，过滤表情/按钮等非媒体资源
        if "/large/" not in large_url:
            return
        if any(x in large_url for x in ("/emoticon/", "donate_btn", "/upload/2016/05/26/319/")):
            return
        parts = large_url.split("/")
        if len(parts) < 2:
            return
        pic_id = parts[-1].split(".")[0]
        if pic_id in image_ids:
            return
        image_ids.add(pic_id)
        if not large_url.endswith((".jpg", ".jpeg", ".png", ".gif")):
            large_url += ".jpg"
        images.append(large_url)

    for img in soup.find_all("img"):
        add_url(img.get("src", ""))

    for link in soup.find_all("a", href=lambda x: x and "oripic" in str(x)):
        href = link.get("href", "")
        if "&u=" in href:
            pic_id_raw = href.split("&u=")[-1].split("&")[0]
            add_url(f"https://wx1.sinaimg.cn/large/{pic_id_raw}")

    return images


