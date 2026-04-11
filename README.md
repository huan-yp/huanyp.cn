# huanyp.cn

## 中文 ID

幻影彭、彭彭

## 英文 ID

huan-yp、huan_yp、huanyp、huan_yp2002、huanyingpeng、hyp

## 曾用头像

![猫](https://raw.githubusercontent.com/huan-yp/image_space/master/img/202604111835867.jpg)

![合照V2X4](https://raw.githubusercontent.com/huan-yp/image_space/master/img/202604111920770.png)

![笛子](https://raw.githubusercontent.com/huan-yp/image_space/master/img/202604111933377.jpg)

## 自动部署

本站使用 GitHub Actions 自动部署到 GitHub Pages，配置见 `.github/workflows/deploy.yml`。

**触发条件**：

- 推送到 `main` 分支时自动触发
- 也可在 GitHub Actions 页面手动触发（workflow_dispatch）

**前提配置**：

- 仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**
- 确保自定义域名 `huanyp.cn` 在 Pages 设置中正确配置（`source/CNAME` 文件已有）

## 静态资源放置

### 本地静态资源

如果需要在博客中引用本地静态文件（PDF、JS、CSS、图片等），放在 `source/` 目录下即可，Hexo 生成时会原样复制到 `public/`。

| 资源需求 | 放置位置 | 访问 URL |
|---------|---------|---------|
| 全局静态文件 | `source/` 下任意位置（非 `_` 开头） | `https://huanyp.cn/<相对路径>` |
| 示例：放一个 PDF | `source/files/resume.pdf` | `https://huanyp.cn/files/resume.pdf` |
| 自定义页面 | `source/<目录>/index.md` | `https://huanyp.cn/<目录>/` |

**注意事项**：

- `source/` 下以 `_` 开头的目录（如 `_posts/`、`_data/`）是 Hexo 特殊目录，不会直接复制到输出

