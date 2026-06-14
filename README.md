# WW.WIKI

WW.WIKI 是一个个人品牌站，定位是市场分析、用户洞察、项目推进和真实写作的组合展示。

## 目录结构

```text
/index.html                  首页
/about.html                  关于我
/projects.html               项目与洞察列表
/thoughts.html               博客列表
/2026/                       真实博客文章
/archive/                    项目案例详情
/templates/                  新增内容模板
/styles/site.css             全站统一样式
```

## 设计规则

- 全站统一使用同一套网格背景、毛玻璃卡片、导航栏、按钮与间距系统。
- 字体体系统一为 `Manrope` + `Noto Serif SC`。
- 全站鼠标样式已经写进 `styles/site.css`，不需要额外脚本。
- 新页面要继续复用 `styles/site.css`，不要在单页里重新发散一套样式。

## 新增博客文章

1. 复制 `templates/blog-post-template.html` 到 `2026/` 目录。
2. 修改这几个位置：
   - `<title>`
   - `<p class="kicker">`
   - `<h1 class="article-title">`
   - `<p class="meta-line">`
   - `<div class="rich-text">`
3. 在 `thoughts.html` 和首页 `index.html` 里补上链接。

推荐文件名：

```text
/2026/日期+标题.html
```

## 新增项目案例

1. 复制 `templates/project-case-template.html` 到 `archive/` 目录。
2. 修改这几个位置：
   - `<title>`
   - `<p class="kicker">`
   - `<h1 class="article-title">`
   - `<p class="lead">`
   - `<div class="chip-row">`
   - `<div class="rich-text">`
3. 在 `projects.html` 和首页 `index.html` 里补上链接。

推荐文件名：

```text
/archive/slug.html
```

## 目录结构能不能改

可以改，而且现在已经按更合理的方式整理好了：

- 博客文章放在 `/2026/`
- 项目案例放在 `/archive/`

这样不会导致跳转异常，只要内部链接继续使用站内根路径或相对路径即可。

## 如何提交

```bash
git add .
git commit -m "Update content and templates"
git push
```

如果你已经在 `brand-polish-homepage` 分支上，直接 `git push` 就会上传当前版本。
