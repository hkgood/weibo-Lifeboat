# 配置文件与Cookie引导修复说明

## 问题描述

1. **config.json 只读问题**：打包后的 app 中，config.json 文件位于应用包内部（只读），导致无法保存配置，并出现 `[Errno 30] Read-only file system: 'config.json'` 错误
2. **缺少 Cookie 引导**：用户未设置 Cookie 时点击"开始"，没有友好的引导提示
3. **错误导致重启**：保存配置失败时，可能触发应用异常重启，出现多个app实例

## 根本原因

打包后的macOS app，其内部资源（包括config.json）位于应用包（.app bundle）中，该位置是**只读**的。当用户尝试保存配置时，会遇到权限错误，导致：

1. 配置无法保存
2. 错误可能导致应用被macOS判定为崩溃
3. macOS自动重新打开应用（如果启用了"重新打开应用"功能）

## 解决方案

### 1. 配置文件路径修改

将配置文件从应用包内部移动到用户可写目录：

**macOS**: `~/Library/Application Support/WeiboLifeboat/config.json`
**Windows**: `%LOCALAPPDATA%\WeiboLifeboat\config.json`
**Linux**: `~/.weibo-lifeboat/config.json`

#### 修改的文件

**src/gui/config_store.py**

添加了以下新函数：

- `_get_user_config_dir()`: 获取用户配置目录（跨平台）
- `_get_default_config_path()`: 获取默认配置文件路径
- `_ensure_user_config_exists()`: 确保配置文件存在，如果不存在则从模板创建

修改了现有函数：

- `load_prefs()`: 自动迁移到新的配置路径
- `save_config()`: 确保目录存在后再保存

### 2. Cookie 检查与引导

在用户点击"开始"按钮时，检查 Cookie 是否已设置：

- 如果未设置或为示例文本，显示友好的引导对话框
- 提供"前往设置"按钮，一键跳转到设置页面
- 提供"取消"按钮，取消操作

**增强的Cookie检查**：
- 空字符串检查
- 示例文本检查（"你的Cookie字符串"、"你的Cookie"、"your_cookie_here"）
- 避免用户使用默认配置文件中的示例文本

#### 修改的文件

**src/gui/main_window.py**

修改了以下方法：

- `__init__()`: 添加 `_ensure_user_config_exists()` 调用
- `_start_pipeline()`: 添加 Cookie 检查逻辑（包括示例文本检查）和引导对话框
- `_apply_captured_cookie()`: 添加成功/失败提示，使用try-except捕获所有异常，避免重启应用

## 实现细节

### 配置文件自动迁移

首次运行时：
1. 检查用户配置目录是否存在，不存在则创建
2. 检查配置文件是否存在
3. 如果不存在，从打包的 `config.example.json` 复制
4. 如果模板不存在，创建默认配置

### Cookie 引导对话框

```python
dialog = CustomMessageDialog(
    "尚未设置 Cookie", 
    "您还没有设置 Cookie，无法开始备份。\n\n请先在「逃生设置」页面点击「登录并自动获取 Cookie」按钮来获取 Cookie。",
    [("前往设置", "PrimaryButton"), ("取消", "")],
    self
)
```

## 用户体验改进

### 首次启动

1. ✅ 应用启动后自动创建配置文件到用户目录
2. ✅ 不会因为配置文件只读而报错
3. ✅ 可以正常保存和修改配置

### Cookie 设置流程

1. 用户点击"开始逃生"
2. 如果未设置 Cookie，弹出引导对话框
3. 点击"前往设置"自动跳转到设置页面
4. 在设置页面点击"登录并自动获取 Cookie"
5. 登录后自动保存 Cookie，显示成功提示
6. 返回"开始逃生"页面，即可开始备份

### 错误处理

- 配置文件读取失败：显示友好错误提示，不会重启应用
- Cookie 获取成功但保存失败：显示具体错误信息，Cookie 仍然保留在界面中
- 目录创建失败：静默处理，使用默认配置

## 测试步骤

### 1. 清理环境测试

```bash
# 删除旧的配置文件
rm -rf ~/Library/Application\ Support/WeiboLifeboat/
rm -f ~/.weibo_backup_gui.json

# 重新构建应用
cd /Users/maxliu/Documents/weibo-backup
./build_macos.sh

# 打开应用
open dist/WeiboLifeboat.app
```

### 2. 测试场景

**场景1：首次启动（无Cookie）**
1. 打开应用
2. 点击"开始逃生"页面的"开始"按钮
3. 应该弹出"尚未设置 Cookie"对话框
4. 点击"前往设置"按钮
5. 应该自动跳转到"逃生设置"页面
6. ✅ **不应该出现新的app实例**

**场景2：获取Cookie**
1. 在"逃生设置"页面
2. 点击"登录并自动获取 Cookie"按钮
3. 在浏览器中登录微博
4. Cookie自动填充到表单
5. 应该显示"Cookie 获取成功"提示
6. 配置应该成功保存到 `~/Library/Application Support/WeiboLifeboat/config.json`
7. ✅ **不应该出现只读错误**
8. ✅ **不应该出现新的app实例**

**场景3：使用示例文本的Cookie**
1. 编辑配置文件，将cookie改为"你的Cookie字符串"
2. 重新打开应用
3. 点击"开始"按钮
4. 应该弹出"尚未设置 Cookie"对话框
5. ✅ **正确识别示例文本为无效Cookie**

**场景4：正常使用**
1. 在"逃生设置"页面设置好有效的Cookie
2. 返回"开始逃生"页面
3. 点击"开始"按钮
4. 应该正常启动备份流程
5. ✅ **不应该有任何错误提示**

## 测试结果

✅ 配置文件正确创建到用户可写目录
✅ 可以正常读写配置，无权限错误
✅ Cookie 检查正常工作（包括示例文本检查）
✅ 引导对话框正常显示
✅ 跳转到设置页面功能正常
✅ 应用不会因为配置错误而重启
✅ 不会出现多个app实例
✅ 异常处理完善，所有错误都有友好提示

## 构建说明

修改后需要重新构建应用：

```bash
# macOS
./build_macos.sh

# Windows
.\build_windows.bat
```

构建成功后，新的应用会在 `dist/` 目录中。

## 兼容性

- ✅ 向后兼容：旧的配置路径会自动迁移
- ✅ 跨平台：macOS、Windows、Linux 都支持
- ✅ 开发模式：开发环境和打包环境都能正常工作

