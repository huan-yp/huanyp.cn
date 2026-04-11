# Blog Writer

QQ 消息驱动的博文交互式写作系统（NcatBot 插件）。

## 安装

1. 将 `plugins/blog-writer/` 放入 NcatBot 的 `plugins/` 目录
2. 复制 `config_template.toml` 为你的配置文件，填写 LLM、图床、博客仓库路径
3. 安装 Python 依赖：`pip install langchain langchain-openai requests`
4. 安装 Puppeteer：`cd preview && npm install`

## 使用

QQ 群中发送：

- `/blog Docker 网络模式详解` — 开始写作
- `ok` — 确认当前段落
- `改 第二段太长了` — 修改反馈
- `预览` — 全文预览截图
- `发布` — git push 发布
- `退出` — 结束会话

## 开发

```bash
cd plugins/blog-writer
python -m pytest tests/ -v
```
