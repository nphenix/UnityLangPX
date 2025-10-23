# UnityLangPX 发布清单

本文档提供了UnityLangPX项目发布的详细步骤和检查清单。

## 发布前准备

### 1. 代码清理 ✅
- [x] 删除桌面应用相关代码
- [x] 清理测试数据和开发文件
- [x] 更新.gitignore文件
- [x] 确保代码质量

### 2. 文档准备 ✅
- [x] 用户使用指南
- [x] 快速开始指南
- [x] API参考文档
- [x] 更新日志
- [x] README.md更新

### 3. 测试验证 ✅
- [x] 核心功能测试
- [x] 集成测试
- [x] 性能测试

## 发布步骤

### 步骤1：创建发布分支
```bash
git checkout -b release/v1.0.0
```

### 步骤2：更新版本号
更新`pyproject.toml`中的版本号：
```toml
[tool.poetry]
name = "unitylangpx"
version = "1.0.0"
```

### 步骤3：提交更改
```bash
git add .
git commit -m "Release v1.0.0"
```

### 步骤4：创建Git标签
```bash
git tag -a v1.0.0 -m "UnityLangPX v1.0.0 Release"
```

### 步骤5：推送到远程仓库
```bash
git push origin release/v1.0.0
git push origin v1.0.0
```

### 步骤6：创建GitHub Release
1. 访问GitHub仓库页面
2. 点击"Releases"选项卡
3. 点击"Create a new release"
4. 选择v1.0.0标签
5. 填写发布标题：`UnityLangPX v1.0.0`
6. 填写发布说明（可使用CHANGELOG.md内容）
7. 点击"Publish release"

### 步骤7：创建PyPI包（可选）
如果您想将项目发布到PyPI：

```bash
# 安装构建工具
pip install build twine

# 构建包
python -m build

# 上传到PyPI
python -m twine upload dist/*
```

## 发布后任务

### 1. 合并分支
```bash
git checkout main
git merge release/v1.0.0
git push origin main
```

### 2. 更新文档
- 更新网站文档
- 发布博客文章（如果有）
- 在社区发布公告

### 3. 用户支持
- 监控用户反馈
- 处理问题和bug报告
- 准备下一版本计划

## 发布检查清单

- [ ] 代码已清理，无开发文件
- [ ] 文档已更新并完整
- [ ] 所有测试通过
- [ ] 版本号已更新
- [ ] Git标签已创建
- [ ] GitHub Release已创建
- [ ] 发布说明已填写
- [ ] 分支已合并
- [ ] 用户已通知

## 常见问题

### Q: 如何回滚发布？
A: 如果发现问题，可以：
1. 创建新版本修复问题
2. 或删除GitHub Release和Git标签，重新发布

### Q: 如何管理版本号？
A: 推荐使用语义化版本控制（SemVer）：
- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

### Q: 如何处理发布后的bug？
A: 
1. 评估bug严重程度
2. 创建修复分支
3. 发布补丁版本（如v1.0.1）

## 联系信息

如有发布相关问题，请通过以下方式联系：
- GitHub Issues
- 邮箱：[您的邮箱]