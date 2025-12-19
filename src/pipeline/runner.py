from __future__ import annotations

import argparse
import asyncio
import json
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
from loguru import logger

try:
    # 兼容：python -m src.pipeline.runner
    from src.database import Database  # type: ignore
    from src.html_generator import HTMLGenerator  # type: ignore
    from src.media_downloader import MediaDownloader  # type: ignore
    from src.weibo_fetcher import WeiboFetcher  # type: ignore
except Exception:
    # 兼容：python src/main.py（此时 sys.path[0] 是 src/）
    from database import Database  # type: ignore
    from html_generator import HTMLGenerator  # type: ignore
    from media_downloader import MediaDownloader  # type: ignore
    from weibo_fetcher import WeiboFetcher  # type: ignore

from .http_utils import AntiBotTriggered, HttpRetryPolicy, get_with_retries
from .events import PipelineEventSink
from .weibo_cn_parser import (
    classify_retweet_from_list_card,
    extract_forward_reason_from_detail,
    extract_images_from_soup,
    extract_text_html_preserve_links,
)


@dataclass(frozen=True)
class PipelineConfig:
    # list fetch
    stop_after_no_new_pages: int = 3
    max_pages: Optional[int] = None

    # detail enrich
    retweet_long_comment_threshold: int = 100
    detail_batch_size: int = 200
    detail_concurrency: int = 3
    detail_retry: HttpRetryPolicy = HttpRetryPolicy()

    # safety
    antibot_fail_fast: bool = True
    antibot_cooldown_seconds: int = 1800  # 30min
    antibot_max_cooldowns: int = 3

    # retweet recheck (A: 修复已有数据库)
    retweet_recheck_year: Optional[int] = None
    retweet_recheck_mode: str = "video_phrase"  # video_phrase | all_original
    retweet_recheck_limit: int = 500

    # detail backfill (历史回填)
    detail_backfill_before_year: Optional[int] = None  # e.g. 2020 => backfill <=2019


def _load_config(config_path: Path) -> Dict[str, Any]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    # Keep the path around for UI/diagnostics without changing user config schema.
    cfg["_config_path"] = str(config_path)
    return cfg


def _build_headers(cfg: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    wcfg = cfg["weibo"]
    user_id = wcfg["user_id"]
    headers = {
        "User-Agent": wcfg["user_agent"],
        "Cookie": wcfg["cookie"],
        "Referer": "https://weibo.cn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    return user_id, headers


def _detail_url(user_id: str, weibo_id: str) -> str:
    clean = weibo_id.replace("M_", "")
    return f"https://weibo.cn/{user_id}/{clean}"


def _classify_from_text_heuristic(text: str) -> Tuple[int, str]:
    """
    仅在“不重复抓取”的前提下，用于补齐 is_retweet 缺失的保守启发式。
    """
    t = (text or "").strip()
    if not t:
        return 0, "original_heuristic"
    if "转发理由" in t or "转发了" in t or t.startswith("转发微博"):
        return 1, "retweet_heuristic"
    if "//@" in t or " //@".replace(" ", "") in t:
        return 1, "retweet_heuristic"
    return 0, "original_heuristic"


class WeiboPipeline:
    def __init__(
        self,
        *,
        config_path: Path,
        pipeline_cfg: PipelineConfig,
        events: PipelineEventSink = PipelineEventSink.disabled(),
    ):
        self.cfg = _load_config(config_path)
        self.pipeline_cfg = pipeline_cfg
        self.events = events

        weibo_cfg = self.cfg["weibo"]
        crawler_cfg = self.cfg["crawler"]
        storage_cfg = self.cfg["storage"]

        self.db = Database(storage_cfg["database_path"])
        self.fetcher = WeiboFetcher(
            user_id=weibo_cfg["user_id"],
            cookie=weibo_cfg["cookie"],
            user_agent=weibo_cfg["user_agent"],
            config=crawler_cfg,
        )
        self.downloader = MediaDownloader(
            config={**storage_cfg, **crawler_cfg},
            headers={"User-Agent": weibo_cfg["user_agent"], "Referer": "https://weibo.cn/"},
        )
        self.html_generator = HTMLGenerator(config=storage_cfg)

    async def run(self, phases: List[str]) -> None:
        try:
            self.events.emit(
                "run_started",
                phases=phases,
                config_path=str(self.cfg.get("_config_path", "")),
            )
            if "list" in phases:
                self.events.emit("phase_started", phase="list")
                await self.phase_list_fetch()
                self.events.emit("phase_completed", phase="list")
            if "detail" in phases:
                self.events.emit("phase_started", phase="detail")
                await self.phase_detail_enrich()
                self.events.emit("phase_completed", phase="detail")
            if "media" in phases:
                self.events.emit("phase_started", phase="media")
                await self.phase_download_media()
                self.events.emit("phase_completed", phase="media")
            if "html" in phases:
                self.events.emit("phase_started", phase="html")
                self.phase_generate_html()
                self.events.emit("phase_completed", phase="html")
            self.events.emit("run_completed", ok=True)
        finally:
            self.db.close()
            self.events.close()

    async def phase_list_fetch(self) -> None:
        last_page = self.db.get_progress("last_page")
        start_page = int(last_page) + 1 if last_page else 1

        logger.info(f"[list] 从第 {start_page} 页开始增量抓取（不会重复入库）")
        self.events.emit("list_started", start_page=start_page)

        page = start_page
        no_new_pages = 0
        new_total = 0

        while True:
            if self.pipeline_cfg.max_pages and (page - start_page + 1) > self.pipeline_cfg.max_pages:
                logger.info(f"[list] 达到 max_pages={self.pipeline_cfg.max_pages}，停止")
                self.events.emit("list_stopped", reason="max_pages", page=page)
                break

            data = await self.fetcher.fetch_user_weibos(page)
            if not data:
                logger.info(f"[list] 第 {page} 页无数据或失败，停止")
                self.events.emit("list_stopped", reason="no_data", page=page)
                break

            cards = data.get("data", {}).get("cards", [])
            if not cards:
                logger.info(f"[list] 第 {page} 页无更多数据，完成")
                self.events.emit("list_stopped", reason="no_cards", page=page)
                break

            page_weibos: List[Dict[str, Any]] = []
            for c in cards:
                if c.get("card_type") != 9:
                    continue
                w = c.get("mblog")
                if w:
                    page_weibos.append(w)

            if not page_weibos:
                logger.info(f"[list] 第 {page} 页无有效微博，停止")
                self.events.emit("list_stopped", reason="no_valid_weibos", page=page)
                break

            new_count = 0
            for w in page_weibos:
                wid = w.get("id")
                if not wid:
                    continue
                if self.db.weibo_exists(wid):
                    continue
                # 新微博：直接入库（包含 is_truncated/is_retweet/html_with_links 等增量字段）
                if self.db.save_weibo(w):
                    new_count += 1
                    new_total += 1
                    # 图片/视频记录入库（去重）
                    for img in w.get("images", []) or []:
                        self.db.save_image(wid, img)
                    for vid in w.get("videos", []) or []:
                        if isinstance(vid, dict) and vid.get("url"):
                            self.db.save_video(wid, vid["url"], vid.get("cover"))

            self.db.set_progress("last_page", str(page))
            logger.info(f"[list] 第 {page} 页新增 {new_count} 条（累计新增 {new_total}）")
            self.events.emit(
                "list_page",
                page=page,
                new_count=new_count,
                new_total=new_total,
                no_new_pages=no_new_pages,
            )

            if new_count == 0:
                no_new_pages += 1
                if no_new_pages >= self.pipeline_cfg.stop_after_no_new_pages:
                    logger.info(
                        f"[list] 连续 {no_new_pages} 页无新增，智能停止（避免重复抓取）"
                    )
                    self.events.emit(
                        "list_stopped",
                        reason="no_new_pages",
                        page=page,
                        no_new_pages=no_new_pages,
                    )
                    break
            else:
                no_new_pages = 0

            page += 1
        self.events.emit("list_completed", last_page=page, new_total=new_total)

    async def phase_detail_enrich(self) -> None:
        """
        - 补全文：is_truncated=1 且 detail_fetched=0/NULL
        - 补转发标记：is_retweet IS NULL（不重复抓取：detail_fetched=1 的只做文本启发式）
        """
        user_id, headers = _build_headers(self.cfg)
        wcfg = self.cfg["weibo"]
        crawler_cfg = self.cfg["crawler"]

        # 忽略 bs4 的 XMLParsedAsHTMLWarning（遇到非标准页面时可能出现；我们也会做内容级反爬检测）
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

        total_batches = 0
        total_done = 0

        timeout = httpx.Timeout(float(crawler_cfg.get("timeout", 30.0)))
        # 详情页更容易触发反爬：优先使用 crawler.request_delay 作为基础节奏
        detail_policy = HttpRetryPolicy(
            max_attempts=self.pipeline_cfg.detail_retry.max_attempts,
            base_delay=float(crawler_cfg.get("request_delay", 1.0)),
            jitter=self.pipeline_cfg.detail_retry.jitter,
            backoff_base=self.pipeline_cfg.detail_retry.backoff_base,
            antibot_statuses=self.pipeline_cfg.detail_retry.antibot_statuses,
        )

        cooldowns = 0
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            while True:
                # 先做“完全不联网”的缺失补齐（detail_fetched=1 的不重复抓取）
                missing = self.db.list_weibos_missing_retweet_flag(limit=self.pipeline_cfg.detail_batch_size)
                patched_heur = 0
                for item in missing:
                    if int(item.get("detail_fetched") or 0) == 1:
                        is_retweet, cat = _classify_from_text_heuristic(item.get("text") or "")
                        self.db.update_weibo_fields(
                            item["id"],
                            {
                                "is_retweet": int(is_retweet),
                                "retweet_category": cat,
                                "fetched_at": datetime.now().isoformat(),
                            },
                        )
                        patched_heur += 1
                if patched_heur:
                    logger.info(f"[detail] 离线启发式补齐 is_retweet：{patched_heur} 条（不重复抓取）")

                # 需要抓详情页的集合：补全文 + 缺失转发标记且未抓详情
                need_detail_ids = set(self.db.list_weibos_needing_detail(limit=self.pipeline_cfg.detail_batch_size))
                for item in missing:
                    if int(item.get("detail_fetched") or 0) == 0:
                        need_detail_ids.add(item["id"])

                # 方案A：对既有数据库做“转发纠错”复核（不新增列）
                if self.pipeline_cfg.retweet_recheck_year is not None:
                    cands = self.db.list_retweet_recheck_candidates(
                        year=int(self.pipeline_cfg.retweet_recheck_year),
                        limit=int(self.pipeline_cfg.retweet_recheck_limit),
                        mode=str(self.pipeline_cfg.retweet_recheck_mode or "video_phrase"),
                    )
                    for wid in cands:
                        brief = self.db.get_weibo_brief(wid) or {}
                        if int(brief.get("detail_fetched") or 0) == 0:
                            need_detail_ids.add(wid)

                # 历史回填：对某个年份之前的所有微博补抓一次详情页（不区分原创/转发）
                if self.pipeline_cfg.detail_backfill_before_year is not None:
                    backfill_ids = self.db.list_weibos_detail_unfetched_before_year(
                        before_year=int(self.pipeline_cfg.detail_backfill_before_year),
                        limit=int(self.pipeline_cfg.detail_batch_size),
                    )
                    need_detail_ids.update(backfill_ids)

                # 方案A（范围版）：如果没指定单年，但指定了历史回填范围，可顺手把该范围内“原创候选”加入复核（用于纠错）
                if (
                    self.pipeline_cfg.retweet_recheck_year is None
                    and self.pipeline_cfg.detail_backfill_before_year is not None
                ):
                    cands2 = self.db.list_retweet_recheck_candidates_before_year(
                        before_year=int(self.pipeline_cfg.detail_backfill_before_year),
                        limit=int(self.pipeline_cfg.retweet_recheck_limit),
                        mode=str(self.pipeline_cfg.retweet_recheck_mode or "video_phrase"),
                    )
                    for wid in cands2:
                        brief = self.db.get_weibo_brief(wid) or {}
                        if int(brief.get("detail_fetched") or 0) == 0:
                            need_detail_ids.add(wid)

                if not need_detail_ids:
                    if total_batches == 0:
                        logger.info("[detail] 无需抓取详情页的任务，跳过")
                    else:
                        logger.info(f"[detail] 本轮已完成全部详情补抓：批次={total_batches} 成功更新={total_done} 条")
                    self.events.emit(
                        "detail_completed",
                        batches=total_batches,
                        total_done=total_done,
                    )
                    return

                total_batches += 1
                batch_ids = sorted(need_detail_ids)
                logger.info(
                    f"[detail] 批次 {total_batches}: 需要抓取详情页：{len(batch_ids)} 条（并发={self.pipeline_cfg.detail_concurrency}）"
                )
                self.events.emit(
                    "detail_batch_started",
                    batch=total_batches,
                    total=len(batch_ids),
                    concurrency=self.pipeline_cfg.detail_concurrency,
                )
                sem = asyncio.Semaphore(self.pipeline_cfg.detail_concurrency)
                done = 0
                last_emit = time.monotonic()

                async def work(wid: str) -> None:
                    nonlocal done
                    nonlocal last_emit
                    url = _detail_url(user_id, wid)
                    try:
                        async with sem:
                            resp = await get_with_retries(
                                client,
                                url,
                                headers=headers,
                                policy=detail_policy,
                                antibot_fail_fast=self.pipeline_cfg.antibot_fail_fast,
                            )
                    except AntiBotTriggered:
                        raise
                    except Exception as e:
                        # 单条失败不应导致整批退出（保持可续跑）
                        logger.warning(f"[detail] 单条详情抓取失败 wid={wid} err={type(e).__name__}: {e}")
                        return

                    if resp.status_code != 200:
                        return

                    body = (resp.text or "").strip()
                    body_lower = body.lower()

                    # 200 也可能是验证码/频繁访问提示页
                    if any(s in body for s in ("验证码", "请输入验证码", "访问过于频繁", "请稍后再试")):
                        raise AntiBotTriggered(f"anti-bot page(200) url={url}")

                    # 有些详情页会明确返回“不存在/已删除”（内容已删除/不可访问）。这类属于“终态”，应打 checkpoint 避免反复补抓。
                    if (
                        ("does not exist" in body_lower)
                        or ("微博不存在" in body)
                        or ("该微博不存在" in body)
                        or ("此微博不存在" in body)
                        or ("该微博已被删除" in body)
                        or ("此微博已被删除" in body)
                        or ("已被作者删除" in body)
                    ):
                        brief = self.db.get_weibo_brief(wid) or {}
                        raw = {}
                        try:
                            raw = json.loads(brief.get("raw_json") or "{}")
                        except Exception:
                            raw = {}
                        raw["detail_missing"] = True
                        raw["detail_missing_reason"] = "missing_or_deleted"
                        self.db.update_weibo_fields(
                            wid,
                            {
                                "raw_json": json.dumps(raw, ensure_ascii=False),
                                "detail_fetched": 1,
                                "fetched_at": datetime.now().isoformat(),
                            },
                        )
                        done += 1
                        now = time.monotonic()
                        if done == len(batch_ids) or done % 25 == 0 or (now - last_emit) >= 1.0:
                            last_emit = now
                            self.events.emit(
                                "detail_batch_progress",
                                batch=total_batches,
                                done=done,
                                total=len(batch_ids),
                            )
                        return

                    # XHTML 用 lxml 的 HTML 解析器即可（warning 已被过滤）
                    soup = BeautifulSoup(body, "lxml")
                    card = soup.find("div", id=wid) or soup.find("div", class_="c", id=True)
                    if not card:
                        # 没找到正文卡片：如果文本提示是“已删除/不存在”，也打终态 checkpoint；否则留给下次重试
                        t = soup.get_text("\n", strip=True).lower()
                        if "does not exist" in t or "不存在" in t or "已被删除" in t or "作者删除" in t:
                            brief = self.db.get_weibo_brief(wid) or {}
                            raw = {}
                            try:
                                raw = json.loads(brief.get("raw_json") or "{}")
                            except Exception:
                                raw = {}
                            raw["detail_missing"] = True
                            raw["detail_missing_reason"] = "missing_or_deleted(no_card)"
                            self.db.update_weibo_fields(
                                wid,
                                {
                                    "raw_json": json.dumps(raw, ensure_ascii=False),
                                    "detail_fetched": 1,
                                    "fetched_at": datetime.now().isoformat(),
                                },
                            )
                            done += 1
                            now = time.monotonic()
                            if done == len(batch_ids) or done % 25 == 0 or (now - last_emit) >= 1.0:
                                last_emit = now
                                self.events.emit(
                                    "detail_batch_progress",
                                    batch=total_batches,
                                    done=done,
                                    total=len(batch_ids),
                                )
                        return

                    content_span = card.find("span", class_="ctt")
                    text, html = extract_text_html_preserve_links(content_span) if content_span else ("", "")
                    images = extract_images_from_soup(soup)

                    # 分类：基于详情页卡片
                    is_forward, _meta = classify_retweet_from_list_card(card)
                    if is_forward:
                        _, reason_len, _src = extract_forward_reason_from_detail(card)
                        if reason_len > self.pipeline_cfg.retweet_long_comment_threshold:
                            is_retweet = 0
                            category = "long_comment"
                        else:
                            is_retweet = 1
                            category = "retweet"
                    else:
                        is_retweet = 0
                        category = "original"

                    # 更新 DB（允许用详情页完整正文覆盖）
                    brief = self.db.get_weibo_brief(wid) or {}
                    raw = {}
                    try:
                        raw = json.loads(brief.get("raw_json") or "{}")
                    except Exception:
                        raw = {}
                    if html:
                        raw["html_with_links"] = html
                    if text:
                        raw["text_detail"] = text

                    self.db.update_weibo_fields(
                        wid,
                        {
                            "text": text or (brief.get("text") or ""),
                            "raw_json": json.dumps(raw, ensure_ascii=False),
                            "is_retweet": int(is_retweet),
                            "retweet_category": category,
                            "detail_fetched": 1,
                            "fetched_at": datetime.now().isoformat(),
                        },
                    )
                    for u in images:
                        self.db.save_image(wid, u)
                    done += 1
                    now = time.monotonic()
                    if done == len(batch_ids) or done % 25 == 0 or (now - last_emit) >= 1.0:
                        last_emit = now
                        self.events.emit(
                            "detail_batch_progress",
                            batch=total_batches,
                            done=done,
                            total=len(batch_ids),
                        )

                try:
                    await asyncio.gather(*(work(wid) for wid in batch_ids))
                except AntiBotTriggered as e:
                    cooldowns += 1
                    logger.error(f"[detail] 触发反爬：{e}")
                    self.events.emit(
                        "antibot_triggered",
                        phase="detail",
                        cooldown_seconds=self.pipeline_cfg.antibot_cooldown_seconds,
                        cooldowns=cooldowns,
                        max_cooldowns=self.pipeline_cfg.antibot_max_cooldowns,
                        error=str(e),
                    )
                    if cooldowns > self.pipeline_cfg.antibot_max_cooldowns:
                        logger.error(f"[detail] 冷却次数已达上限（{self.pipeline_cfg.antibot_max_cooldowns}），停止以避免浪费时间")
                        self.events.emit("detail_stopped", reason="antibot_max_cooldowns")
                        return
                    logger.warning(f"[detail] 进入冷却：{self.pipeline_cfg.antibot_cooldown_seconds}s 后自动继续（第 {cooldowns}/{self.pipeline_cfg.antibot_max_cooldowns} 次）")
                    await asyncio.sleep(float(self.pipeline_cfg.antibot_cooldown_seconds))
                    continue

                logger.info(f"[detail] 批次完成：{done}/{len(batch_ids)}")
                self.events.emit(
                    "detail_batch_completed",
                    batch=total_batches,
                    done=done,
                    total=len(batch_ids),
                )
                total_done += done
                if done == 0:
                    logger.warning("[detail] 本批次 0 条成功更新，停止以避免无限循环（可能是登录失效或触发反爬）")
                    self.events.emit("detail_stopped", reason="zero_success")
                    return

    async def phase_download_media(self) -> None:
        images = self.db.get_undownloaded_images()
        if images:
            logger.info(f"[media] 待下载图片：{len(images)} 张")
            total = len(images)
            self.events.emit("media_images_started", total=total)
            last_emit = time.monotonic()

            def on_img_progress(done: int, total_: int) -> None:
                nonlocal last_emit
                now = time.monotonic()
                if done == total_ or done % 10 == 0 or (now - last_emit) >= 1.0:
                    last_emit = now
                    self.events.emit("media_images_progress", done=done, total=total_)

            results = await self.downloader.download_images_batch(images, progress_cb=on_img_progress)
            for image_id, local_path in results:
                if local_path:
                    self.db.update_image_path(image_id, local_path)
            self.events.emit("media_images_completed", total=total)
        else:
            logger.info("[media] 图片已全部下载")
            self.events.emit("media_images_completed", total=0)

        videos = self.db.get_undownloaded_videos()
        if videos:
            logger.info(f"[media] 待下载视频：{len(videos)} 个")
            total = len(videos)
            self.events.emit("media_videos_started", total=total)
            last_emit = time.monotonic()

            def on_vid_progress(done: int, total_: int) -> None:
                nonlocal last_emit
                now = time.monotonic()
                if done == total_ or done % 5 == 0 or (now - last_emit) >= 1.0:
                    last_emit = now
                    self.events.emit("media_videos_progress", done=done, total=total_)

            results = await self.downloader.download_videos_batch(videos, progress_cb=on_vid_progress)
            for video_id, local_path in results:
                if local_path:
                    self.db.update_video_path(video_id, local_path)
            self.events.emit("media_videos_completed", total=total)
        else:
            logger.info("[media] 视频已全部下载")
            self.events.emit("media_videos_completed", total=0)

    def phase_generate_html(self) -> None:
        weibos = self.db.get_all_weibos(order_by="created_at DESC")
        images_map = {w["id"]: self.db.get_weibo_images(w["id"]) for w in weibos}
        videos_map = {w["id"]: self.db.get_weibo_videos(w["id"]) for w in weibos}
        stats = self.db.get_statistics()
        self.html_generator.generate(weibos, images_map, videos_map, stats)


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Weibo backup incremental pipeline")
    ap.add_argument("--config", default="config.json", help="config path")
    ap.add_argument(
        "--phases",
        default="list,detail,media,html",
        help="comma-separated: list,detail,media,html",
    )
    ap.add_argument("--stop-after-no-new-pages", type=int, default=3)
    ap.add_argument("--max-pages", type=int, default=0, help="0 means unlimited")
    ap.add_argument("--detail-batch-size", type=int, default=200)
    ap.add_argument("--detail-concurrency", type=int, default=3)
    ap.add_argument("--retweet-threshold", type=int, default=100)
    ap.add_argument("--antibot-cooldown-seconds", type=int, default=1800)
    ap.add_argument("--antibot-max-cooldowns", type=int, default=3)
    ap.add_argument("--retweet-recheck-year", type=int, default=0, help="0 disables; e.g. 2024")
    ap.add_argument("--retweet-recheck-mode", default="video_phrase", help="video_phrase|all_original")
    ap.add_argument("--retweet-recheck-limit", type=int, default=500)
    ap.add_argument("--detail-backfill-before-year", type=int, default=0, help="0 disables; e.g. 2020 => backfill <=2019")
    ap.add_argument(
        "--events-jsonl",
        default="",
        help="Write JSONL progress events to this path. Use '-' for stdout. Empty disables.",
    )
    return ap


async def main(argv: Optional[List[str]] = None) -> None:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    cfg = PipelineConfig(
        stop_after_no_new_pages=max(1, int(args.stop_after_no_new_pages)),
        max_pages=(int(args.max_pages) if int(args.max_pages) > 0 else None),
        detail_batch_size=max(1, int(args.detail_batch_size)),
        detail_concurrency=max(1, int(args.detail_concurrency)),
        retweet_long_comment_threshold=max(1, int(args.retweet_threshold)),
        antibot_cooldown_seconds=max(60, int(args.antibot_cooldown_seconds)),
        antibot_max_cooldowns=max(1, int(args.antibot_max_cooldowns)),
        retweet_recheck_year=(int(args.retweet_recheck_year) if int(args.retweet_recheck_year) > 0 else None),
        retweet_recheck_mode=str(args.retweet_recheck_mode or "video_phrase"),
        retweet_recheck_limit=max(1, int(args.retweet_recheck_limit)),
        detail_backfill_before_year=(
            int(args.detail_backfill_before_year) if int(args.detail_backfill_before_year) > 0 else None
        ),
    )
    events = PipelineEventSink.from_target(str(args.events_jsonl or ""))
    pipeline = WeiboPipeline(config_path=Path(args.config), pipeline_cfg=cfg, events=events)
    phases = [p.strip() for p in (args.phases or "").split(",") if p.strip()]
    await pipeline.run(phases)


if __name__ == "__main__":
    asyncio.run(main())


def run_pipeline_from_gui(
    config_path: Path,
    phases: List[str],
    stop_after_no_new_pages: int,
    max_pages: int,
    detail_batch_size: int,
    detail_concurrency: int,
    retweet_threshold: int,
    antibot_cooldown_seconds: int,
    antibot_max_cooldowns: int,
    event_callback: Any,
    log_callback: Any,
    should_stop: Any,
) -> int:
    """
    GUI-friendly entry point that runs pipeline in current thread.
    
    Args:
        config_path: Path to config.json
        phases: List of phases to run (e.g., ["list", "detail", "media", "html"])
        *: Pipeline configuration parameters
        event_callback: Function to call with event dict
        log_callback: Function to call with log strings
        should_stop: Function that returns True if pipeline should stop
        
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # 首先为当前线程创建并设置event loop（在初始化任何异步组件之前）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 创建自定义事件sink，将事件转发到GUI
        class GUIEventSink:
            def emit(self, event: str, **data: Any) -> None:
                try:
                    event_callback({"event": event, "data": data, "ts": time.time()})
                except Exception as e:
                    log_callback(f"[ERROR] Failed to emit event: {e}")
            
            def close(self) -> None:
                pass
        
        cfg = PipelineConfig(
            stop_after_no_new_pages=max(1, stop_after_no_new_pages),
            max_pages=(max_pages if max_pages > 0 else None),
            detail_batch_size=max(1, detail_batch_size),
            detail_concurrency=max(1, detail_concurrency),
            retweet_long_comment_threshold=max(1, retweet_threshold),
            antibot_cooldown_seconds=max(60, antibot_cooldown_seconds),
            antibot_max_cooldowns=max(1, antibot_max_cooldowns),
        )
        
        events = GUIEventSink()
        # 现在可以安全地创建 WeiboPipeline，因为 event loop 已经设置好了
        pipeline = WeiboPipeline(config_path=config_path, pipeline_cfg=cfg, events=events)  # type: ignore
        
        # 运行pipeline
        try:
            loop.run_until_complete(pipeline.run(phases))
            return 0
        finally:
            loop.close()
    
    except Exception as e:
        log_callback(f"[ERROR] Pipeline execution failed: {e}")
        import traceback
        log_callback(traceback.format_exc())
        try:
            loop.close()
        except Exception:
            pass
        return 1



