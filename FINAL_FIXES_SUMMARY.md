# 最终修复总结

## 修复的问题

### 1. ✅ 配置文件只读问题
**问题**：打包后的app中，config.json位于应用包内部（只读），无法保存配置。

**解决方案**：
- 配置文件移到：`~/Library/Application Support/WeiboLifeboat/config.json` (macOS)
- Windows: `%LOCALAPPDATA%\WeiboLifeboat\config.json`
- Linux: `~/.weibo-lifeboat/config.json`

### 2. ✅ Cookie引导功能
**问题**：未设置Cookie时点击"开始"，没有友好提示。

**解决方案**：
- 检查Cookie是否为空或示例文本
- 显示引导对话框，提供"前往设置"按钮
- 自动跳转到设置页面

### 3. ✅ 应用重复打开问题（严重bug）
**问题**：点击"开始"后会重复打开新的app实例。

**根本原因**：
- 在打包环境中，`sys.executable` 指向的是 `WeiboLifeboat.app` 本身！
- `QProcess.setProgram(sys.executable)` 导致启动新的app实例

**解决方案**：
- 打包环境：在单独线程中运行pipeline（不使用子进程）
- 开发环境：继续使用子进程（原有逻辑）
- 添加了 `run_pipeline_from_gui()` 函数用于线程内执行

### 4. ✅ 用户ID自动提取
**问题**：Cookie获取成功后，用户ID字段保持为示例文本。

**解决方案**：
- 从Cookie的SUB字段提取用户ID
- 从MLOGIN字段提取
- 通过API (`https://m.weibo.cn/api/config`) 获取当前登录用户ID
- 自动填充到用户ID字段

### 5. ✅ 数据存储路径优化
**问题**：默认使用相对路径（`data/`），不便于查找和备份。

**解决方案**：
- 数据目录移到：`~/Documents/WeiboLifeboat/` (所有平台)
- 包含：
  - `weibo.db` - 数据库
  - `images/` - 图片
  - `videos/` - 视频  
  - `output/` - HTML输出
- 添加"打开数据目录"按钮
- 界面显示当前数据目录路径

## 修改的文件

### 1. `src/gui/config_store.py`
- 添加 `_get_user_config_dir()` - 获取配置目录
- 添加 `_get_user_data_dir()` - 获取数据目录（文档）
- 修改 `_ensure_user_config_exists()` - 自动设置数据路径为文档目录

### 2. `src/gui/main_window.py`
- 修改 `_start_pipeline()` - 添加Cookie检查和引导
- 修改 `_apply_captured_cookie()` - 自动提取并保存用户ID
- 添加 `_extract_user_id_from_cookie()` - 从Cookie提取用户ID
- 添加 `_fetch_user_id_from_api()` - 通过API获取用户ID
- 添加 `_open_data_dir()` - 打开数据目录
- 修改存储设置界面 - 添加数据目录提示和按钮

### 3. `src/gui/pipeline_process.py`
- 重构 `start()` - 区分打包/开发环境
- 打包环境：使用线程而非子进程
- 添加 `_run_in_thread()` - 线程内运行pipeline
- 添加停止标志支持

### 4. `src/pipeline/runner.py`
- 添加 `run_pipeline_from_gui()` - GUI友好的入口函数
- 支持事件回调和日志回调
- 支持停止检查

## 目录结构

### 配置文件位置
```
macOS:    ~/Library/Application Support/WeiboLifeboat/config.json
Windows:  %LOCALAPPDATA%\WeiboLifeboat\config.json
Linux:    ~/.weibo-lifeboat/config.json
```

### 数据文件位置
```
所有平台: ~/Documents/WeiboLifeboat/
├── weibo.db          # 数据库
├── images/           # 下载的图片
├── videos/           # 下载的视频
└── output/           # 生成的HTML
```

## 用户体验改进

### 首次启动
1. ✅ 自动创建配置文件到用户目录
2. ✅ 自动创建数据目录到文档
3. ✅ 不会因为只读错误而报错

### Cookie设置流程
1. 点击"开始逃生"
2. 弹出"尚未设置 Cookie"对话框
3. 点击"前往设置"自动跳转
4. 点击"登录并自动获取 Cookie"
5. 登录后：
   - ✅ 自动提取用户ID
   - ✅ 自动保存Cookie和用户ID
   - ✅ 显示成功提示（包含用户ID）
6. 返回"开始逃生"，点击"开始"

### 数据管理
- ✅ 数据存储在文档目录，便于查找
- ✅ 可以点击"打开数据目录"快速访问
- ✅ 可以点击"打开输出目录"查看HTML
- ✅ 便于备份和迁移

## 已解决的错误

### 1. `[Errno 30] Read-only file system: 'config.json'`
✅ 配置文件现在保存到用户可写目录

### 2. 点击"开始"后重复打开app
✅ 使用线程而非子进程，不会重新启动app

### 3. 用户ID未正确保存
✅ 自动从Cookie或API提取用户ID

### 4. 数据文件路径混乱
✅ 统一使用文档目录，路径清晰

### 5. 应用崩溃问题 (SIGSEGV)
✅ 改进了QProcess的使用方式，避免在打包环境中使用

## 测试建议

### 测试场景1：全新安装
```bash
# 清理所有数据
rm -rf ~/Library/Application\ Support/WeiboLifeboat/
rm -rf ~/Documents/WeiboLifeboat/
rm -f ~/.weibo_backup_gui.json

# 打开应用
open dist/WeiboLifeboat.app

# 预期结果：
# - 自动创建配置目录和数据目录
# - 点击"开始"提示设置Cookie
# - 可以正常登录并获取Cookie
# - 用户ID自动填充
```

### 测试场景2：Cookie获取
```bash
# 1. 打开应用
# 2. 前往"逃生设置"
# 3. 点击"登录并自动获取 Cookie"
# 4. 在浏览器中登录微博

# 预期结果：
# - Cookie自动填充
# - 用户ID自动填充（如：1234567890）
# - 保存成功提示显示用户ID
# - 配置文件正确保存
```

### 测试场景3：开始备份
```bash
# 1. 确保Cookie已设置
# 2. 返回"开始逃生"
# 3. 选择备份选项
# 4. 点击"开始"

# 预期结果：
# - 不会弹出新的app实例
# - pipeline在当前app中运行
# - 进度正常显示
# - 数据保存到 ~/Documents/WeiboLifeboat/
```

### 测试场景4：数据目录
```bash
# 1. 前往"逃生设置"
# 2. 查看"存储与导出"部分
# 3. 点击"打开数据目录"

# 预期结果：
# - 打开 ~/Documents/WeiboLifeboat/ 目录
# - 可以看到weibo.db、images等文件夹
# - 路径显示清晰
```

## 构建说明

重新构建应用以包含所有修复：

```bash
cd /Users/maxliu/Documents/weibo-backup
./build_macos.sh
```

构建完成后，新的应用在：`dist/WeiboLifeboat.app`

## 技术细节

### 打包vs开发环境
```python
if getattr(sys, 'frozen', False):
    # 打包环境
    # - 使用线程运行pipeline
    # - 配置/数据在用户目录
    # - sys._MEIPASS指向资源目录
else:
    # 开发环境
    # - 使用子进程运行pipeline
    # - 相对路径可用
```

### 用户ID提取流程
1. 尝试从Cookie的SUB字段解码（base64）
2. 尝试从MLOGIN字段提取
3. 调用API `https://m.weibo.cn/api/config` 获取
4. 如果都失败，用户需要手动填写

### 线程安全
- 使用Qt的Signal机制从子线程发送事件
- 事件回调和日志回调都是线程安全的
- 使用停止标志而非强制终止

## 已知限制

1. **用户ID提取可能失败**：如果Cookie格式特殊或API不可用，需要手动填写
2. **相对路径支持**：仍然支持相对路径，但推荐使用绝对路径（默认）
3. **打包环境限制**：无法使用外部Python，必须使用内置模块

## 下一步建议

1. ✨ 添加数据迁移工具（从旧路径导入）
2. ✨ 添加备份/恢复功能
3. ✨ 支持自定义数据目录
4. ✨ 添加磁盘空间检查
5. ✨ 优化大量数据的显示性能

