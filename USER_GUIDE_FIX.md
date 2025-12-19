# 修复完成 - 用户指南

## 已修复的问题

✅ **配置文件只读错误**：配置文件现在保存到用户可写目录，不会再出现权限错误
✅ **Cookie引导**：未设置Cookie时，会友好提示并引导到设置页面
✅ **应用重复打开**：修复了可能导致多个app实例的问题

## 配置文件新位置

**macOS**: `~/Library/Application Support/WeiboLifeboat/config.json`

您可以随时修改和保存配置，不会再有权限问题。

## 使用流程

### 第一次使用

1. **打开应用**
   - 双击 `WeiboLifeboat.app`
   - 应用会自动创建配置文件

2. **设置Cookie**（两种方式）：

   **方式一：自动获取（推荐）**
   - 点击左侧"逃生设置"
   - 点击"登录并自动获取 Cookie"按钮
   - 在弹出的浏览器中登录微博
   - Cookie自动保存

   **方式二：手动粘贴**
   - 在浏览器中登录 https://m.weibo.cn
   - 按F12打开开发者工具
   - 在Console中输入 `document.cookie` 并回车
   - 复制结果并粘贴到应用的Cookie字段

3. **开始备份**
   - 返回"开始逃生"页面
   - 选择需要的备份选项
   - 点击"开始"按钮

### Cookie检查

如果您忘记设置Cookie或Cookie无效，点击"开始"时会出现提示：

```
尚未设置 Cookie

您还没有设置 Cookie，无法开始备份。

请先在「逃生设置」页面点击「登录并自动获取 Cookie」按钮来获取 Cookie。

[前往设置]  [取消]
```

点击"前往设置"会自动跳转到设置页面。

## 常见问题

**Q: 为什么我的配置文件不见了？**  
A: 新版本将配置文件移到了用户目录。如果您之前有配置，需要重新设置Cookie。

**Q: Cookie保存失败怎么办？**  
A: 应用会显示具体错误信息。如果问题持续，请检查 `~/Library/Application Support/WeiboLifeboat/` 目录是否可写。

**Q: 点击"开始"后出现多个应用怎么办？**  
A: 这个问题已经修复。如果仍然出现，请：
1. 关闭所有应用实例
2. 清理配置：`rm -rf ~/Library/Application\ Support/WeiboLifeboat/`
3. 重新打开应用

**Q: 如何查看应用日志？**  
A: 日志位于 `~/Library/Logs/WeiboLifeboat/app.log`

## 技术细节

如果您想了解详细的修复内容，请查看 `CONFIG_FIX_SUMMARY.md`

## 重新构建应用

如果您是从源代码构建：

```bash
cd /Users/maxliu/Documents/weibo-backup
./build_macos.sh
```

构建完成后，应用位于 `dist/WeiboLifeboat.app`

