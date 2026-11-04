# Polebug Comments

博客原生评论服务：Cloudflare Worker + 独立 D1 数据库 `polebug-comments`，API 域名 `comments.polebug.com`。不依赖 GitHub Issues 读取或第三方评论 iframe。GitHub 只参与登录；访客经 Turnstile 验证后提交待审核评论。界面跟随博客主题，评论正文第一版以纯文本安全显示，保留换行（历史 Markdown 原文保留，可通过「原评论」查看原格式）。

## 管理和身份

在文章评论面板选择「使用 GitHub 登录」。GitHub 数字 ID `8676289`（polebug）可看到「管理评论」，查看全站待审核、已发布、已隐藏、已删除评论，并发布、隐藏或软删除。读者可以回复及删除自己的评论。访客昵称没有身份验证，界面明确标记；GitHub 用户按稳定数字 ID 识别，不按昵称授权。普通 GitHub 评论直接发布，访客评论审核后公开。

公开接口不返回待审核/隐藏内容。软删除保留审计与回复关系；曾公开的评论只显示删除占位。软删除不是数据彻底清除，管理员仍可查看/恢复正文。彻底清除个人数据需维护者单独执行数据库清理及备份保留策略。

## 数据模型与划线评论

| 表 | 职责 |
| --- | --- |
| documents / document_aliases | 稳定 UUID、当前路径、历史路径，改标题和 URL 不更换文章身份 |
| document_revisions | 不可变正文快照、SHA-256、规范化版本 |
| anchors | 选中文字 exact、前后文 prefix/suffix、原始 revision 与 Unicode 码点位置 |
| anchor_resolutions | 锚点在各修订中的位置与 exact / relocated / ambiguous / orphaned 状态 |
| threads | 文章讨论串（anchor 为空）或划线讨论串（关联 anchor） |
| comments | 内容、所属讨论串、父评论、作者快照、审核状态及外部迁移 ID |
| users / identities | 内部用户与外部身份分离；访客也有独立用户 ID |
| sessions / oauth_states | 哈希会话令牌、CSRF、短期一次性 OAuth state 与 PKCE |
| moderation_events | 操作人、前后状态及时间的审核记录 |
| rate_limits | 短期限流计数；IP 仅存每日加盐哈希 |

`blog/comment-documents.json` 是文章 ID 注册表。**改 slug 时移动原键，保留 UUID**，不要为同一篇文章重新生成 ID。路径是别名，绝不能作为评论唯一身份。原始 GitHub 评论使用唯一 external_id，重复导入不会增加副本或覆盖已审核状态。

构建 HTML 的 `.prose` 经 `hast-util-to-text`、NFC 和 CRLF→LF 生成正文快照，规范化版本 `hast-text-nfc-v1`。偏移量采用 Unicode 码点，左闭右开，不能直接使用 DOM Range 的 UTF-16 下标。未来划线 UI 必须实现同版规范化及 DOM↔文本映射，并提交 revision ID；服务端验证选区对应原文后创建 anchor 和 thread，不能信任客户端坐标。当前 API 仅开放文章级评论，划线交互/写入 API 尚未开放。

`src/anchors.js` 已实现纯函数重定位：原修订匹配优先，否则搜索 exact 并核对前后文。匹配唯一才重定位，多个候选标记 ambiguous，找不到标记 orphaned；不把旧评论悄悄挂到另一处。跨文章的 revision、anchor、回复通过复合外键禁止混用。正文更新追加 revision，不覆盖旧快照；旧锚点永远保留原始证据。

## 本地运行与检查

```sh
npm run comments:register
npm run build
npm run comments:sync
npx --yes wrangler@4.152.0 d1 migrations apply polebug-comments --local --config comments/wrangler.toml
npx --yes wrangler@4.152.0 d1 execute polebug-comments --local --config comments/wrangler.toml --file comments/.data/documents.sql
npm run comments:dev
npm run dev
npm run comments:test
```

本地使用忽略的 `comments/.dev.vars`，设置 ENVIRONMENT=development、BLOG_ORIGIN=http://127.0.0.1:4321、API_ORIGIN=http://127.0.0.1:8788 和本地 RATE_SALT。不要把生产密钥复制进代码。没有 Turnstile 配置时访客写入关闭，不能用开发开关绕过线上验证。GitHub 登录需要与环境对应的 OAuth 回调地址。

测试使用 Node 22 内置 SQLite 运行真实 schema，覆盖权限、CSRF、访客待审核/Turnstile 响应、OAuth state、限流、幂等、分页、跨文章外键和 Unicode 锚点重定位。

## 发布新文章或修改正文

评论数据库需要先同步文章注册和正文快照，再发布博客。以下步骤可重复执行，不更改评论或审核状态：

```sh
npm run comments:register
npm run build
npm run comments:sync
npx --yes wrangler@4.152.0 d1 execute polebug-comments --remote --config comments/wrangler.toml --file comments/.data/documents.sql
# 然后将文章及 blog/comment-documents.json 一起提交，按博客正常流程发布。
```

未注册的文章会构建失败，并明确提示先运行 comments:register，避免线上静默丢失评论。`comments:sync` 从已构建的页面读取最新正文；不要对旧 dist 执行。同步仍是发布前的显式步骤，GitHub Pages 工作流不会自动持有 Cloudflare 写权限。

## 服务部署与配置

```sh
npx --yes wrangler@4.152.0 d1 migrations apply polebug-comments --remote --config comments/wrangler.toml
npx --yes wrangler@4.152.0 deploy --config comments/wrangler.toml
```

Worker secrets：GITHUB_CLIENT_ID、GITHUB_CLIENT_SECRET、TURNSTILE_SITE_KEY、TURNSTILE_SECRET_KEY、RATE_SALT。使用 Wrangler secret put/bulk 从安全输入设置，禁止提交。OAuth 应用名 Polebug Comments，回调 `https://comments.polebug.com/auth/github/callback`，不申请仓库、邮箱 scope。Turnstile 只允许 blog.polebug.com，服务端校验 action=comment 和 hostname。

会话使用 Secure/HttpOnly/SameSite=Lax 的 host-only cookie；生产写入校验 Origin，已登录用户还校验 CSRF。请求大小上限 20KB、正文 6000 字符，按 IP/用户限流。数据库不存 GitHub OAuth access token、邮箱、原始 IP；session 令牌仅存哈希。每日 cron 清理过期会话、登录状态和限流计数。API `no-store` 避免用户状态/私有内容进入共享缓存。

## GitHub 评论迁移与备份

```sh
npm run build
npm run comments:import
# 检查 comments/.data/report.json，再导入：
npx --yes wrangler@4.152.0 d1 execute polebug-comments --remote --config comments/wrangler.toml --file comments/.data/import.sql
```

首次迁移：167 条评论，55 个文档（23 篇当前文章及 32 个历史归档）。只迁移评论映射中的文章 issue；未映射的插件报错 issue 不属于文章评论。历史文章尚未恢复 URL 时归档在 `legacy:github:<issue>`，数据保留供以后绑定。重复执行会追加新 GitHub 评论，不覆盖原生评论及本地审核；不是持续双向同步。原 GitHub issue 不删除。`.data` 包含导出与报告，不入库。

迁移/结构变更前先导出 D1：

```sh
npx --yes wrangler@4.152.0 d1 export polebug-comments --remote --config comments/wrangler.toml --output comments/.data/backup.sql
```

备份包含私有待审核内容及会话信息，需限制访问并加密保存。Cloudflare D1 Time Travel 可辅助恢复，保留期限以当前账户计划为准。回滚前端可恢复 utterances，但切换期间新增的原生评论仍保留在 D1；不要删除数据库。
