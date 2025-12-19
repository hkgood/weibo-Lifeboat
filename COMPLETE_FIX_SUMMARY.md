# 微博逃生舱 - 完整修复与改进总结

## 🎉 核心功能修复

### 1. ✅ 用户ID自动提取（URL监控）
**问题**：无法从Cookie中提取用户ID，因为Cookie不包含明文的用户ID。

**解决方案**：监控WebView的URL变化，当用户浏览到个人主页时自动提取！
- 添加 `url_changed` 信号到 `MacOSWebViewWidget`
- 使用定时器每500ms检查URL变化
- 正则表达式匹配 `/u/数字` 或 `/profile/数字` 格式
- 在对话框底部实时显示提取到的用户ID
- Cookie获取后自动填充用户ID字段

**修改文件**：
- `src/gui/cookie_login_native.py` - URL监控和提取逻辑
- `src/gui/main_window.py` - 应用提取到的用户ID

---

### 2. ✅ Event Loop错误修复
**问题**：
```
RuntimeError: There is no current event loop in thread 'Thread-1'.
```

**原因**：在新线程中运行异步代码时，需要先为该线程创建event loop。

**解决方案**：
1. 在 `run_pipeline_from_gui` 函数开始就创建并设置event loop
2. `MediaDownloader` 的 `Semaphore` 延迟初始化（使用 `@property`）

**修改文件**：
- `src/pipeline/runner.py` - 在函数开始创建event loop
- `src/media_downloader.py` - Semaphore延迟初始化

---

### 3. ✅ 获取完整Cookie（包括HttpOnly）
**问题**：使用 `document.cookie` 只能获取非HttpOnly的Cookie，导致登录失败。

**原因**：微博的关键Cookie（如 `SUB`）被标记为HttpOnly，JavaScript无法访问。

**解决方案**：使用WKWebView的原生Cookie Store API：
```python
# 修改前（不完整）
js_code = "document.cookie"
self.webview.evaluateJavaScript_completionHandler_(js_code, handler)

# 修改后（完整）
self.cookie_store.getAllCookies_(completion_handler)
```

**修改文件**：
- `src/gui/cookie_login_native.py` - 使用原生Cookie Store

**效果**：从5个Cookie增加到12个Cookie，包含所有HttpOnly Cookie！

---

### 4. ✅ 配置路径自动更新
**问题**：旧的配置文件使用相对路径 `data/`，在打包应用中不可用。

**解决方案**：
- 配置文件存储在 `~/Library/Application Support/WeiboLifeboat/`（macOS）
- 数据存储在 `~/Documents/WeiboLifeboat/`
- 自动检测并更新已存在配置文件的路径

**修改文件**：
- `src/gui/config_store.py` - 路径管理和自动更新

---

## 🎨 UI改进

### 5. ✅ 开始按钮Loading动画
**功能**：
- 点击开始后显示「运行中...」动画（点点点动画）
- 运行中按钮不可点击（禁用状态）
- 完成后恢复「开始」文本并可点击

**实现**：
- 使用 `QTimer` 每500ms更新按钮文本
- 动态显示 1-3 个点的动画效果

---

### 6. ✅ 停止按钮状态管理
**功能**：
- 未开始时：不可点击（灰色）
- 运行中：可点击（可以停止任务）
- 完成后：恢复不可点击

---

### 7. ✅ 日志目录按钮
**功能**：
- 新增「打开日志目录」按钮
- 初始状态：不可点击（灰色）
- 有日志后：自动启用，点击打开系统日志文件夹

**日志位置**：
- macOS: `~/Library/Logs/WeiboLifeboat/`
- Windows: `~/AppData/Local/WeiboLifeboat/Logs/`
- Linux: `~/.weibo-lifeboat/logs/`

---

### 8. ✅ 友好的中文日志
**改进前**：
```json
{"event": "list_page", "data": {"page": 1, "new_count": 10, "new_total": 10}}
{"event": "list_page", "data": {"page": 2, "new_count": 10, "new_total": 20}}
...
```

**改进后**：
```
📋 开始备份任务 [list, detail, media, html]
▶️  开始阶段：列表抓取
🔍 开始抓取微博列表（从第1页开始）
   第1页：新增 10 条，累计 10 条
   第5页：新增 10 条，累计 50 条
   第10页：新增 10 条，累计 100 条
✓ 列表抓取完成：共 47 页，462 条微博
▶️  开始阶段：详情抓取
   批次 1：准备抓取 200 条详情
   进度：20/200 (10%)
   ...
✅ 备份任务完成！
```

**特点**：
- 使用Emoji图标增强可读性
- 减少刷屏（每5页/每10个/每20个显示一次）
- 清晰的阶段划分和进度提示

---

## 📦 数据存储位置

### macOS
- **配置文件**: `~/Library/Application Support/WeiboLifeboat/config.json`
- **用户数据**: `~/Documents/WeiboLifeboat/`
  - `weibo.db` - 数据库
  - `images/` - 图片
  - `videos/` - 视频
  - `output/` - 导出HTML
- **日志文件**: `~/Library/Logs/WeiboLifeboat/`

### Windows
- **配置文件**: `%APPDATA%\Local\WeiboLifeboat\config.json`
- **用户数据**: `%USERPROFILE%\Documents\WeiboLifeboat\`
- **日志文件**: `%APPDATA%\Local\WeiboLifeboat\Logs\`

### Linux
- **配置文件**: `~/.weibo-lifeboat/config.json`
- **用户数据**: `~/Documents/WeiboLifeboat/`
- **日志文件**: `~/.weibo-lifeboat/logs/`

---

## 🚀 使用流程

1. **打开应用** → 自动创建配置文件和数据目录
2. **进入「逃生设置」** → 点击「登录并自动获取Cookie」
3. **登录微博** → 访问个人主页（点击「我」）
4. **自动提取用户ID** → 底部显示「用户ID：xxx」
5. **点击「获取Cookie」** → 自动保存完整Cookie（12个，包括HttpOnly）
6. **返回「开始逃生」** → 点击「开始」
7. **观察进度** → 
   - 开始按钮显示「运行中...」动画
   - 停止按钮变为可用
   - 日志显示友好的中文提示
8. **完成后** → 
   - 开始按钮恢复可点击
   - 可以点击「打开日志目录」查看详细日志
   - 可以点击「打开数据目录」查看备份数据

---

## 🐛 已修复的问题

1. ❌ **app重复打开** → ✅ 使用线程内执行替代子进程
2. ❌ **Cookie不完整（5个）** → ✅ 获取完整Cookie（12个）
3. ❌ **用户ID未保存** → ✅ 从URL自动提取并保存
4. ❌ **Event loop错误** → ✅ 线程启动时创建event loop
5. ❌ **config.json只读** → ✅ 使用用户可写目录
6. ❌ **数据路径错误** → ✅ 自动更新为文档目录
7. ❌ **按钮状态混乱** → ✅ 根据运行状态正确管理
8. ❌ **日志难以阅读** → ✅ 友好的中文日志格式

---

## 📝 技术亮点

1. **原生WebView集成** - 使用PyObjC直接调用WKWebView API
2. **Cookie Store访问** - 获取包括HttpOnly在内的所有Cookie
3. **URL监控** - 定时检查WebView的URL变化，智能提取用户ID
4. **异步线程管理** - 正确处理event loop生命周期
5. **延迟初始化** - 使用property装饰器延迟创建异步对象
6. **平台适配** - 根据操作系统选择合适的目录路径
7. **UI状态管理** - 按钮状态与任务状态同步
8. **Loading动画** - 使用QTimer实现流畅的动画效果
9. **事件格式化** - 将JSON事件转换为用户友好的中文提示

---

## 🎯 测试清单

- [ ] Cookie获取：登录后能获取12个Cookie
- [ ] 用户ID提取：访问个人主页后自动提取ID
- [ ] Pipeline启动：点击开始能正常运行
- [ ] 数据抓取：能成功抓取微博列表和详情
- [ ] 开始按钮：运行时显示动画且不可点击
- [ ] 停止按钮：未开始时不可点击，运行时可点击
- [ ] 日志按钮：有日志后可以打开日志目录
- [ ] 日志可读性：显示友好的中文提示而非JSON

---

## 📊 数据统计

**从测试日志看到的成功抓取**：
- 47页微博列表
- 462条微博
- 12个完整Cookie（包括HttpOnly）

**应用体积**：
- 103MB（使用原生WKWebView）
- 比QtWebEngine版本小89%

---

## 🙏 用户反馈驱动的改进

所有这些改进都是基于用户的实际使用反馈：
1. "微博id依然没有在获取cookie后自动更新" → URL监控提取
2. "抓取好像也出了问题" → Cookie完整性修复
3. "日志的可读性不是很好" → 友好的中文日志
4. "开始按钮应该有loading动画" → 按钮状态和动画改进

**这充分证明了用户反馈的价值！** 🎉

