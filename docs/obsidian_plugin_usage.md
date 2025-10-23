# UnityLangPX Obsidian插件使用指南

## 安装和配置

### 1. 安装插件

1. 将编译后的插件文件复制到Obsidian插件目录
2. 在Obsidian中启用UnityLangPX插件

### 2. 启动翻译服务

在使用插件之前，需要先启动翻译服务：

```bash
# 启动HTTP API服务器
unitylangpx serve

# 或者指定端口
unitylangpx serve --port 8848
```

### 3. 配置插件

1. 在Obsidian中打开设置
2. 找到UnityLangPX插件设置
3. 配置服务地址（默认：http://localhost:8848）
4. 设置源语言和目标语言
5. 选择默认文件处理方式

## 使用方法

### 翻译单个文件

1. 在文件浏览器中右键点击Markdown文件
2. 选择"UnityLangPX翻译" → "翻译当前文件"
3. 在弹出的对话框中确认翻译选项
4. 等待翻译完成

### 批量翻译

1. 在文件浏览器中选择多个Markdown文件
2. 右键点击选中的文件
3. 选择"UnityLangPX翻译" → "翻译选中文件"
4. 确认翻译选项
5. 等待批量翻译完成

### 查看翻译历史

1. 使用命令面板（Ctrl/Cmd + P）
2. 输入"UnityLangPX"
3. 选择"显示翻译历史"

## API接口

插件通过HTTP API与翻译服务通信，主要接口包括：

### 服务状态检查

```http
GET /api/service/status
```

### 文本翻译

```http
POST /api/translate/text
Content-Type: application/json

{
  "text": "Hello, world!",
  "source_language": "en",
  "target_language": "zh",
  "preserve_formatting": true
}
```

### 文件翻译

```http
POST /api/translate/file
Content-Type: application/json

{
  "file_path": "/path/to/file.md",
  "content": "# Title\n\nContent...",
  "source_language": "en",
  "target_language": "zh",
  "output_mode": "suffix",
  "overwrite": false
}
```

### 批量翻译

```http
POST /api/translate/batch
Content-Type: application/json

{
  "files": ["/path/to/file1.md", "/path/to/file2.md"],
  "output_dir": "/path/to/output",
  "source_language": "en",
  "target_language": "zh",
  "overwrite": false
}
```

## 故障排除

### 服务连接失败

1. 确保翻译服务已启动
2. 检查服务地址和端口是否正确
3. 确认防火墙没有阻止连接

### 翻译失败

1. 检查Ollama服务是否运行
2. 确认翻译模型已下载
3. 查看插件日志获取详细错误信息

### 文件处理错误

1. 确认文件权限正确
2. 检查输出目录是否存在
3. 确认磁盘空间充足

## 高级配置

### 自定义端口

如果8848端口被占用，可以指定其他端口：

```bash
unitylangpx serve --port 8849
```

然后在插件设置中更新服务地址。

### 后台运行

使用`--daemon`参数可以在后台运行服务：

```bash
unitylangpx serve --daemon
```

### 环境变量

可以通过环境变量配置默认参数：

```bash
export UNITYLANGPX_PORT=8848
export UNITYLANGPX_HOST=localhost
unitylangpx serve