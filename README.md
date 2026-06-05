# 我的个人博客操作手册

## 如何添加一篇新文章并在主页显示

### 第一步：创建新文章的 HTML 文件
/2026内有“example”文件，直接复制粘贴到新文章.html

### 第二步：在首页 index.html 的文章列表中添加新文章的链接
回到仓库根目录，打开 index.html 文件，点击编辑（铅笔图标）

找到 <div class="content"> 里面的文章列表区域

在最顶部（或合适位置）添加一个新的 <div class="post-container"> 块：

html
<div class="post-container">
    <p class="post-title"><a href="/2026/你的文章文件名.html">文章标题</a></p>
    <p class="post-meta"><span class="date meta-item">Posted at 2026-06-05</span></p>
    <p class="post-abstract">文章简短摘要</p>
</div>
点击 Commit changes 保存。

### 第三步：更新归档页面
打开 /archives/index.html，在对应年份的 <ul> 列表中添加一条 <li> 链接，保持归档页完整。

### 上传图片：将图片放入 /images 文件夹，然后在文章中用 <img src="/images/图片名.jpg"> 引用。
