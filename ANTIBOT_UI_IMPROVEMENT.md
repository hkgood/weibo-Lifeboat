# 反爬虫提示优化说明

## 问题描述

当微博抓取过程中触发反爬虫机制（HTTP 403 错误）时，GUI界面的日志中只显示原始的JSON事件数据，不够友好。

示例原始事件：
```json
{"event": "antibot_triggered", "data": {"cooldown_seconds": 1800, "cooldowns": 1, "error": "anti-bot status=403 url=https://weibo.cn/1787199825/Qj26Rybvz", "max_cooldowns": 3, "phase": "detail"}}
```

## 解决方案

在 `src/gui/main_window.py` 的 `_format_event_friendly()` 函数中添加了对以下事件的友好显示支持：

### 1. `antibot_triggered` 事件

当触发反爬虫机制时，显示：
```
⚠️  触发反爬虫机制（详情抓取）
   将等待 30 分钟后自动继续... (1/3 次)
```

显示内容包括：
- 触发反爬虫的阶段（列表抓取/详情抓取/媒体下载）
- 等待时间（自动转换为分钟）
- 当前触发次数和最大允许次数

### 2. `detail_stopped` 事件增强

添加了对两种停止原因的友好提示：

- 当达到最大冷却次数时：
  ```
  ⚠️  详情抓取停止：触发反爬虫次数过多，已自动停止
  ```

- 当批次无成功更新时：
  ```
  ⚠️  详情抓取停止：本批次无成功更新
  ```

## 用户体验改进

**之前：**
用户看到类似这样的原始JSON：
```
{"event": "antibot_triggered", "data": {"cooldown_seconds": 1800, ...}}
```

**现在：**
用户看到清晰的中文提示：
```
⚠️  触发反爬虫机制（详情抓取）
   将等待 30 分钟后自动继续... (1/3 次)
```

## 技术细节

修改文件：`src/gui/main_window.py`

在 `_format_event_friendly()` 函数中添加了：
1. `antibot_triggered` 事件的处理逻辑
2. `detail_stopped` 事件的增强处理（区分不同的停止原因）

事件处理流程：
1. Pipeline runner 触发反爬虫时发出 `antibot_triggered` 事件
2. GUI 的 `_on_event()` 接收到事件
3. `_format_event_friendly()` 将事件转换为友好的中文提示
4. `_append_log()` 显示在日志窗口中

## 相关代码

- 事件发出：`src/pipeline/runner.py` 第 528-535 行
- 事件处理：`src/gui/main_window.py` 第 1065-1080 行
- 事件定义：`src/pipeline/events.py`

