# UnityLangPX 简易发布指南

本指南专为不熟悉Git和GitHub发布流程的用户设计，将指导您完成UnityLangPX项目的发布。

## 前置准备

确保您已安装Git并配置了GitHub账户。

## 第一步：创建发布分支

打开命令行工具（CMD、PowerShell或Git Bash），进入项目目录：

```bash
cd e:/UnityLangPX
```

创建并切换到发布分支：

```bash
git checkout -b release/v1.0.0
```

## 第二步：提交所有更改

将所有更改添加到Git：

```bash
git add .
```

提交更改：

```bash
git commit -m "Release v1.0.0"
```

## 第三步：推送到GitHub

将分支推送到GitHub：

```bash
git push origin release/v1.0.0
```

## 第四步：创建GitHub Release（网页操作）

1. 打开浏览器，访问您的GitHub仓库页面
2. 点击仓库页面顶部的"Releases"选项卡
3. 点击"Create a new release"按钮
4. 在"Choose a tag"下拉菜单中，输入`v1.0.0`
5. 在"Release title"中输入：`UnityLangPX v1.0.0`
6. 在"Describe this release"文本框中，粘贴[RELEASE_NOTES.md](RELEASE_NOTES.md)的内容
7. 点击"Publish release"按钮

## 第五步：创建Git标签

回到命令行，创建Git标签：

```bash
git tag -a v1.0.0 -m "UnityLangPX v1.0.0 Release"
```

推送标签到GitHub：

```bash
git push origin v1.0.0
```

## 第六步：合并到主分支

切换回主分支：

```bash
git checkout main
```

合并发布分支：

```bash
git merge release/v1.0.0
```

推送主分支：

```bash
git push origin main
```

## 完成！

🎉 恭喜！您已成功发布UnityLangPX v1.0.0版本。

## 验证发布

1. 访问GitHub仓库的Releases页面，确认v1.0.0版本已显示
2. 检查版本号和发布说明是否正确
3. 确认源代码文件已正确上传

## 常见问题

### Q: 推送时提示身份验证错误
A: 请确保您已配置GitHub的SSH密钥或使用个人访问令牌（Personal Access Token）

### Q: 创建分支时提示错误
A: 确保您已提交当前所有更改，或者使用`git checkout -b release/v1.0.0`强制创建新分支

### Q: 合并分支时出现冲突
A: 如果出现冲突，请解决冲突后再提交，或者联系开发者协助

## 联系支持

如果遇到任何问题，请通过以下方式获取帮助：
- GitHub Issues
- 项目维护者邮箱

---

**提示**：发布后，请通知用户项目已更新，可以在GitHub Releases页面下载最新版本。