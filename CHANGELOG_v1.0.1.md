# 微博逃生舱 v1.0.1 更新日志

发布日期：2024-12-19

## 🎉 重大改进

### 核心功能修复

#### 1. 用户ID自动提取 ✨
- **URL监控提取**：从WebView URL自动识别用户主页并提取用户ID
- **实时显示**：登录对话框底部实时显示提取到的用户ID
- **自动填充**：Cookie获取后自动填充用户ID字段

#### 2. 完整Cookie获取 🔐
- **原生Cookie Store**：使用WKWebView的`getAllCookies`API
- **包含HttpOnly**：获取所有Cookie包括HttpOnly（从5个→12个）
- **登录成功率**：解决了Cookie不完整导致的登录失败问题

#### 3. 线程与异步修复 🔧
- **Event Loop管理**：在线程启动时正确创建和设置event loop
- **延迟初始化**：`MediaDownloader`的`Semaphore`使用property延迟创建
- **进程内执行**：打包应用中直接在线程内运行pipeline，避免重复启动

#### 4. 配置文件路径优化 📁
**macOS**:
- 配置: `~/Library/Application Support/WeiboLifeboat/config.json`
- 数据: `~/Documents/WeiboLifeboat/`
- 日志: `~/Library/Logs/WeiboLifeboat/`

**Windows**:
- 配置: `%APPDATA%\Local\WeiboLifeboat\config.json`
- 数据: `%USERPROFILE%\Documents\WeiboLifeboat\`
- 日志: `%APPDATA%\Local\WeiboLifeboat\Logs\`

**自动迁移**：首次运行自动将相对路径更新为绝对路径

---

## 🎨 UI/UX改进

### 按钮优化
- **Loading动画**：开始按钮显示「运行中...」动画（点点点循环）
- **状态管理**：
  - 开始按钮：运行中禁用且显示动画，完成后恢复
  - 停止按钮：未开始时禁用，运行中启用
  - 清空按钮：无日志时禁用，有日志后启用
- **固定宽度**：所有按钮`min-width: 100px`避免文字变化时跳变
- **完善阴影**：所有状态（启用/禁用/按下）都正确显示阴影
  - 启用: opacity=0.02
  - 禁用: opacity=0.01
  - 按下: opacity=0.015

### 进度显示优化
- **新增列表进度条**：显示「第X页 (Y条)」
- **移除视频进度条**：简化界面（不抓取视频）
- **进度条顺序**：列表 → 详情 → 图片
- **淡化颜色**：进度条使用25%透明度的橙色，文字更清晰

### 日志体验
- **友好的中文日志**：将JSON事件转换为易读的中文提示
- **减少刷屏**：只显示关键进度（每5页/10个/20个）
- **Emoji图标**：📋 🔍 ✓ ✅ 等增强可读性
- **智能清空**：清空按钮根据日志状态自动启用/禁用

---

## 🐛 Bug修复

1. **强制停止状态**：kill后立即更新按钮状态
2. **阴影消失**：使用eventFilter监听状态变化，确保阴影始终显示
3. **Cookie不完整**：使用原生API获取HttpOnly Cookie
4. **用户ID未保存**：从URL提取并自动填充
5. **Event Loop错误**：正确的线程初始化和延迟创建
6. **应用重复打开**：使用线程内执行替代子进程
7. **配置文件只读**：使用用户可写目录

---

## 📊 技术改进

### 代码质量
- **事件过滤器**：`ShadowContainer`使用eventFilter监听按钮状态
- **全局样式**：通过CSS统一控制按钮样式而非逐个设置
- **延迟初始化**：避免在没有event loop时创建异步对象
- **平台适配**：根据操作系统选择合适的目录路径

### 性能优化
- **异步更新**：使用`QTimer.singleShot(0)`避免递归绘制
- **状态缓存**：减少不必要的UI更新

---

## 📦 构建信息

- **应用体积**: 103MB
- **原生WebView**: 使用系统WKWebView，比QtWebEngine小89%
- **依赖**: PySide6, httpx, PyObjC (macOS), lxml等

---

## 🙏 致谢

感谢所有用户的反馈和建议！本次更新的所有改进都来自真实用户的使用反馈。

---

## 📝 已知问题

无

---

## 🔄 升级说明

1. **首次启动**会自动创建新的配置目录
2. **旧配置文件**会自动迁移路径
3. **建议重新登录**获取完整Cookie

---

## 📮 反馈

如遇问题或有建议，欢迎在GitHub提Issue：
https://github.com/[your-username]/weibo-backup/issues

