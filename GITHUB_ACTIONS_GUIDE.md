# GitHub Actions 自动打包使用指南

## 🎯 功能说明

GitHub Actions 已配置完成！它会自动：
- ✅ 在 macOS 和 Windows 上同时打包
- ✅ 创建 DMG（macOS）和 ZIP（Windows）
- ✅ 自动发布到 GitHub Releases
- ✅ 生成详细的 Release Notes

## 🚀 使用方法

### 方法 1：推送版本标签（推荐）

这是最标准的发布流程：

```bash
# 1. 确保所有更改已提交
git add .
git commit -m "Release v1.0.0"

# 2. 创建并推送 tag
git tag v1.0.0
git push origin main
git push origin v1.0.0

# 3. 等待 GitHub Actions 完成（约 5-10 分钟）
# 4. 在 GitHub Releases 页面查看结果
```

**自动化流程：**
1. 推送 tag 后，GitHub Actions 自动启动
2. 同时在 macOS 和 Windows 虚拟机上打包
3. 自动创建 Release 并上传文件
4. 生成 Release Notes

### 方法 2：手动触发

在 GitHub 网站上手动触发（用于测试）：

1. 进入你的仓库
2. 点击 **Actions** 标签
3. 选择左侧 **Build and Release** 工作流
4. 点击右上角 **Run workflow** 按钮
5. 选择分支，点击 **Run workflow**

**注意：** 手动触发不会创建 Release，只会生成构建产物（Artifacts）

---

## 📦 构建产物

### 自动创建的文件

**macOS:**
```
微博逃生舱-1.0.0-macOS.dmg     (~200MB)
```

**Windows:**
```
微博逃生舱-1.0.0-Windows.zip    (~200MB)
```

### 在哪里找到

**推送 tag 后：**
- 自动发布到 **Releases** 页面
- URL: `https://github.com/<你的用户名>/weibo-backup/releases`

**手动触发：**
- 在 **Actions** 页面的工作流运行详情中
- 点击 **Artifacts** 下载

---

## 🎯 完整发布流程示例

```bash
# === 第一次发布 v1.0.0 ===

# 1. 确保代码最新且通过测试
git status
python run_gui.py  # 本地测试

# 2. 提交所有更改
git add .
git commit -m "feat: 完成 v1.0.0 功能"

# 3. 推送到 GitHub
git push origin main

# 4. 创建版本标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 5. 等待 GitHub Actions 完成（5-10 分钟）
# 可以在 GitHub 网站的 Actions 页面实时查看进度

# 6. 完成！访问 Releases 页面下载
```

---

## 📊 GitHub Actions 工作流程

```
推送 v1.0.0 tag
    ↓
GitHub Actions 触发
    ↓
    ├─→ macOS 虚拟机
    │    ├─ 安装 Python 3.9
    │    ├─ 安装依赖
    │    ├─ 运行 PyInstaller
    │    ├─ 创建 DMG
    │    └─ 上传产物
    │
    └─→ Windows 虚拟机
         ├─ 安装 Python 3.9
         ├─ 安装依赖
         ├─ 运行 PyInstaller
         ├─ 创建 ZIP
         └─ 上传产物
    ↓
创建 GitHub Release
    ├─ 生成 Release Notes
    ├─ 上传 macOS DMG
    ├─ 上传 Windows ZIP
    └─ 发布
    ↓
用户可以下载 🎉
```

---

## 🐛 故障排除

### 问题 1：Actions 失败

**查看日志：**
1. 进入 **Actions** 页面
2. 点击失败的工作流
3. 展开失败的步骤，查看详细错误

**常见原因：**
- Python 依赖问题 → 检查 `requirements.txt`
- PyInstaller 错误 → 检查 `.spec` 文件
- 权限问题 → 检查仓库 Settings

### 问题 2：Release 未自动创建

**检查项：**
- ✅ 是否推送了 tag（`git push origin v1.0.0`）
- ✅ tag 格式是否正确（必须以 `v` 开头）
- ✅ 两个构建任务是否都成功

### 问题 3：下载的文件损坏

**解决方案：**
- 重新运行工作流
- 检查构建日志中的警告
- 在本地测试是否能正常打包

---

## ⚙️ 高级配置

### 修改触发条件

编辑 `.github/workflows/build-release.yml`：

```yaml
# 当前配置：推送 v* tag 时触发
on:
  push:
    tags:
      - 'v*'

# 也可以改为：推送到 main 分支时触发
on:
  push:
    branches:
      - main
```

### 添加更多平台

理论上还可以添加 Linux 构建：

```yaml
build-linux:
  name: Build Linux
  runs-on: ubuntu-latest
  steps:
    # ... 类似的步骤
```

### 自定义 Release Notes

修改 `.github/workflows/build-release.yml` 中的 `release_notes.md` 内容。

---

## 💡 最佳实践

### 版本命名规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：

- `v1.0.0` - 主版本.次版本.修订号
- `v1.0.1` - 修复 bug
- `v1.1.0` - 新增功能
- `v2.0.0` - 重大更新

### 发布前检查清单

- [ ] 本地测试通过
- [ ] 更新 README（如有必要）
- [ ] 更新版本号
- [ ] 提交所有更改
- [ ] 创建有意义的 tag message

### Tag 消息示例

```bash
git tag -a v1.0.0 -m "Release v1.0.0

主要特性：
- 原生 WebView 集成
- 体积优化 80%+
- 完整的 macOS 和 Windows 支持
"
```

---

## 📝 费用说明

**完全免费！**

GitHub Actions 对公开仓库完全免费，每月配额：
- ✅ macOS: 无限分钟
- ✅ Windows: 无限分钟
- ✅ Linux: 无限分钟

（私有仓库有限额，但公开项目无限制）

---

## 🎉 总结

配置完成后，你只需要：

```bash
git tag v1.0.0
git push origin v1.0.0
```

剩下的全部自动化！5-10 分钟后，macOS 和 Windows 版本就会出现在 Releases 页面。

这是最专业、最省心的发布方式！🚀

