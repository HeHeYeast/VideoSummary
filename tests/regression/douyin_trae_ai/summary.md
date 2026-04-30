# 搭建全网千万收藏的 AI 第二大脑：TRAE SOLO 实战教程

> **原视频**：[搭建全网千万收藏的 AI 第二大脑，3 分钟教会你！](https://v.douyin.com/D4_5dfVmsIo/)
> **作者**：数字游牧人 Samuel · **时长**：4:12
> **关键词**：TRAE SOLO、Compound Engineering、MTC 模式、Code 模式、个人知识库、Skills

## 这篇教程讲什么

字节跳动的 AI 开发工具 TRAE 在 **SOLO 新版客户端**里推出了 **MTC 模式**（通用任务）和 **Code 模式**（编程），把原本只适用于程序员的 agent 工作流搬给了所有知识工作者。本教程跟着视频作者，一步步在 TRAE SOLO 桌面端搭出一套「摄取 → 消化 → 输出」的 AI 第二大脑，并用 Code 模式的网页端让云端 agent 帮你测试网站、创建 GitHub Issue。

学完你会得到：

- 一个持续生长的本地个人知识库（`raw/` + `wiki/` + `outputs/`）
- 3 条可复用的自定义命令：**摄取**、**消化**、**输出**
- 用技能市场装好的 `youtube-transcript`、`dogfood`、`gh-cli`、`byted-seedream-image-generate` 等 skills
- 一条云端 agent 测试 Web 应用并自动提 Issue 的工作流

---

## 一、先理解核心理念：Compound Engineering

[00:05] **什么是 Compound Engineering**

![](frames/seg_0000_000001.jpg)

视频开头抛出核心概念：**Compound Engineering（复利工程）—— 不是把 AI 当成一次性加速器，而是让每次任务都把经验沉淀成下一次任务的起点。**

核心是一个四步循环：

| 步骤 | 做什么 |
| --- | --- |
| **Plan** | 先规划、拆解任务，不是立刻动手 |
| **Work** | 让 AI 完成具体执行 |
| **Review** | 人或 AI 自己把关质量 |
| **Compound** | 关键一步：把这次经验写回系统，让下次更容易 |

两个容易搞错的点：**沉淀下来的不是这次答案本身，而是被复用的系统资产**；**复利不发生在模型里，复利发生在有没有把判断留下来**。

*为什么重要*：后面要做的 3 个自定义命令（摄取 / 消化 / 输出），本质就是把这张图实现到 TRAE SOLO 的 workspace 里。每运行一次，`wiki/` 都会长厚一点，你的 AI 就越用越聪明。

---

## 二、看清目标：LLM 维护的个人知识库长什么样

[00:45] **三阶段知识库流程：raw → wiki → outputs**

![](frames/seg_0000_000005.jpg)

作者把个人知识库拆成 **摄取 / 消化 / 输出** 三个目录：

- **摄取 `raw/`**：原始资料池 —— 网页、论文、仓库、播客转录、截图剪藏，任何格式原样扔进来
- **消化 `wiki/`**：由 LLM 持续把 `raw/` 里的东西拆成「摘要 / 概念页与主题文章 / 索引回链与分类」，以 Markdown 文件存储，互相建立链接
- **输出 `outputs/`**：在 `wiki/` 基础上生成问答归档、Markdown / 图表、幻灯片等沉淀结果

*核心观点*：**你不直接写 wiki，LLM 才是这个知识库的主要维护者。Obsidian 更像前台 —— 看 raw、看 wiki、看输出，不再是手工文件整理工具。**

![](frames/seg_0088_000002.jpg)

*额外工具*：wiki 长到一定规模后，模型不必每次都重新摘要，而是直接搜索 + 再造文章；再配上搜索 CLI、网页 UI、健康检查器这些系统资产，让 agent 能长期持续调用。

---

## 三、进入 TRAE SOLO 桌面端：打开命令面板

[01:28] **步骤 1：选本地文件夹作为 AI workspace**

![](frames/seg_0000_000008.jpg)

TRAE SOLO 桌面端启动界面，主页面有「应用开发 / 项目理解 / 游戏创意 / 工具脚本」四张卡片。左上角可以在 **Code** 和 **MTC** 两种模式间切换。

先不做应用开发，切换到 **MTC 模式**，然后新建一个项目（作者命名为 `LLM Wiki`），**指定一个本地文件夹作为 AI workspace** —— 这一步非常关键，因为后面所有 `raw/`、`wiki/`、`outputs/` 都会写在这个文件夹里，由你完全掌控。

[01:38] **步骤 2：进入设置 → 命令面板**

![](frames/seg_0088_000001.jpg)

点击左下角头像 → 设置，进入左侧菜单的 **命令** 项。初次进来右边是空的（「暂无命令 · 点击新建以添加你的第一个命令」），我们要在这里创建三条命令：**摄取**、**消化**、**输出**。

*为什么要用命令而不是每次手输 prompt*：命令可以保存指令、描述、技能绑定，下次在对话框里打个 `/` 就能调出来，这就是 Compound 的载体。

---

## 四、创建三条自定义命令

[01:43] **步骤 3：编辑「输出-知识卡片」命令**

![](frames/seg_0088_000003.jpg)

点击右上角「+ 创建」，弹出编辑对话框。作者这里先演示的是 **输出-知识卡片** 命令。重点字段：

- **命令名称**：`输出-知识卡片`
- **描述**：`用于基于 /wiki 中已沉淀的知识生成一张知识卡片。`
- **说明**（核心 prompt）：

> 你负责围绕具体任务调用知识库内容进行输出，请先读取 /wiki 下相关条目，再生成一张知识卡片。输出的必须明确依赖了哪些知识条目；如果知识不足，要指出缺口和补充内容，而不是硬编造。若本次任务产生新的结构化记忆、问答或补充知识，请同步给出建议回写到 /wiki 的内容，让每次输出都能继续增强这个知识系统。

*注意整段 prompt 的结构*：① 任务是什么 ② 读哪个目录 ③ 输出写到哪 ④ **明确要求不足就要补缺口，不准硬编造** ⑤ 每次跑完要回写新的笔记 —— 这五条就是把 Compound Engineering 嵌到 prompt 里的标准模板。

*按同样模板再创建另外两条*：

- **摄取**：读入外部 URL/文件，抓取内容，按来源归档到 `/raw` 下，并把元数据写成 front-matter
- **消化**：遍历 `/raw` 里最近变动的文件，抽取知识点，按 Atomic Notes 拆分写入 `/wiki`，互相建立反向链接

---

## 五、演示「摄取」命令：把 YouTube 视频扒成本地笔记

[01:58] **步骤 4：在 MTC 对话框里输入斜杠调出命令**

![](frames/seg_0088_000005.jpg)

新建任务后，在对话框里输入 `/` 就能弹出刚创建的命令列表。作者这里选了 **摄取** 命令，并附上一条 YouTube 链接：

```
https://www.youtube.com/watch?v=rmvDxxNuBlg
```

这是 AI Engineer 大会上 Dex Horthy 的演讲 *No Vibes Allowed: Solving Hard Problems in Complex Codebases*。MTC 自动做了三件事：

1. **调用技能** `youtube-transcript`
2. **执行命令** `node /mnt/appuserdata/skills/youtube-transcript/transcript.js "https://www.youtube.com/watch?v=..."`
3. 取到的 transcript 存为产物：`/sessions/69d51cf65eb82b1ba189be58/work/transcript_raw.txt`

[02:06] **步骤 5：把原始资料整理成带 front-matter 的笔记**

![](frames/seg_0088_000008.jpg)

agent 继续把 transcript 翻译（英文 → 中文）并拆解成结构化 Markdown，落盘到 `raw/` 目录，文件名 `2025-12-02_No-Vibes-Allowed_上下文工程_复杂代码库.md`。开头自动生成了标准化元数据：

```yaml
---
title: "No Vibes Allowed: Solving Hard Problems in Complex Codebases – Dex Horthy, HumanLayer"
source_name: "AI Engineer（YouTube）"
source_url: "https://www.youtube.com/watch?v=rmvDxxNuBlg"
author: "Dex Horthy"
published_at: 2025-12-02
captured_at: 2026-04-07
content_type: "方法论"
filename: "2025-12-02_No-Vibes-Allowed_上下文工程_复杂代码库.md"
tags:
  - Context Engineering
  - 编码代理
  - 上下文窗口
  - 核心代码库
  - 研究-计划-实现
  - RPI
  - Harness Engineering
  - 团队协作
  - 代码评审
  - 语义扩散
---
```

*为什么这些字段很值钱*：`source_url` / `published_at` 是未来反查的锚点，`tags` 是给消化步骤建立交叉引用用的 —— 没有这些 meta，`wiki/` 就会是一团散文，没法做知识图谱。

---

## 六、演示「消化」命令：生成原子笔记 + 自动建图

[02:15] **步骤 6：运行消化命令，agent 自动制定计划**

![](frames/seg_0088_000011.jpg)

切到一个新任务，调用 `/消化` 命令。agent 先自己列出一个待办清单：

- ☑ 检查 `/raw` 目录并选取最近修改的文件
- ☐ 读取原始文件内容并提取可复用的知识单元
- ☐ 按 Atomic Notes 生成多个 Markdown 原子
- ☐ 为笔记补充标签、相关条目与来源信息

[02:28] **步骤 7：`wiki/` 疯狂生长，自动提取概念页**

![](frames/seg_0088_000013.jpg)

左侧 TRAE 面板可以看到 agent 正在生成的一批 `/wiki` 条目：`按需生成压...`、`计划是意图...`、`心智对齐-代...`、`不要把意外...`、`语义扩散-semantic-diffusion...`、`Harness-Engineering...`。右侧 Obsidian 的 Graph view 显示知识图谱的节点和连线 —— 每个原子笔记都是一个节点，通过 tag 和 `[[wikilink]]` 互相连接。

![](frames/seg_0088_000015.jpg)

展开某个原子笔记 `Harness-Engineering-让代码库更适配编码代理与集成点.md`，结构非常清晰：Properties 区保留来源（`source_path: raw/2025-12-02_No-Vibes-Allowed...`）、tags（`Harness Engineering`、`上下文工程`）、再下面是「核心概念 / 论证 / 描述」正文。

*这就是 Compound 的具象*：每消化一次 `raw/`，`wiki/` 都会多出 5-10 个原子笔记，下次写作就能随机组合调用。

---

## 七、切换 Code 模式：用「输出」命令生成 HTML 知识卡片

[02:27] **步骤 8：切回 Code 模式**

![](frames/seg_0088_000017.jpg)

点左上角把模式从 MTC 切到 **Code**。要生成含 HTML/CSS 的知识卡片，Code 模式能直接看到代码编辑器和行号。这时候 agent 会在思考区做 `Analyzing New Concepts → Mapping Key Components → Synthesizing Template` 的三步规划。

[02:29] **步骤 9：调用「输出-知识卡片」，生成 HTML**

![](frames/seg_0147_000001.jpg)

在 Code 模式输入 `/输出-知识卡片 生成关于 harness engineering 的知识卡片。用中文。`。agent 生成的 HTML 文件，代码编辑器里可以看到 CSS 变量定义：

```css
:root {
  --paper-2: #F7F2EA;
  --ink: #231F1C;
  --ink-light: #5F5751;
  --ink-dim: #8A7D71;
  --stone: #B1A79A;
  --line: #CFC4B8;
  --brick: #B23A36;
  --brick-dark: #8F3B31;
  --serif: 'DM Serif Display', 'Noto Serif SC', Georgia, serif;
  --sans: 'DM Sans', 'PingFang SC', system-ui, sans-serif;
  --mono: 'SF Mono', Menlo, monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1600px; height: 900px; background: var(--wall); }
body { font-family: var(--sans); }
```

*注意*：模板在命令说明里就约束了配色、字体变量、1600×900 尺寸，所以每次生成的卡片都是同一套视觉。这也是 Compound —— **视觉语言被写成了系统资产**。

[02:37] **步骤 10：换个格式再试一次 —— 生成 PDF 文章**

![](frames/seg_0147_000003.jpg)

作者说「算了，写成图文并茂的文章给我吧，看你能输出 pdf 还是什么格式，都可以」。agent 选择了 PDF，并先列出目录规划（共 9 页）：

| 页码 | 内容 |
| --- | --- |
| 1 | 深色封面 + 封面图 |
| 2 | 引言 + 核心理念（高亮金句） |
| 3 | 主循环 + 四步流程彩色表格 + 循环图 |
| 4 | Plan / Work / Review 详细步骤 + Agent 协作图 |
| 5 | Compound 步骤 + 插件系统 |
| 6 | 传统工程 vs 复合工程对比图 |
| 7-8 | 八个需要放下的信念 + 思维转变图 |
| 9 | 过渡期挑战 + 结语金句 |

右边打开了实际生成的 `compound_engineering_article.pdf`，能看到一张带四色节点的循环图（Plan / Work / Review / Compound）。

[02:46] **步骤 11：查看 Obsidian 知识图谱全景**

![](frames/seg_0147_000006.jpg)

Obsidian Graph view 展示整个个人知识库：数百个节点密集连在一起。作者在此总结贯穿全片的金句：**「任何一个正经的大项目，必然需要一个 workspace，随着任务的推进不断生长，变成长期的资产。不要再把 AI 当做一次性的对话窗口。」**

---

## 八、技能市场

[02:34] **步骤 12：打开技能市场**

![](frames/seg_0147_000004.jpg)

TRAE SOLO 的 **技能市场**（左栏「技能」）分为「全部 / 开发工具 / 数据分析 / 界面设计 / 内容创作 / 效率提升」。作者已经装了：

| 技能名 | 作者 | 用途 |
| --- | --- | --- |
| `composition-patterns` | Vercel | React 组合模式设计指南（含 React 19 更新） |
| `frontend-design` | Anthropic | 构建生产级质量的前端界面，避免 AI 审美趋同 |
| `gh-cli` | Github | GitHub CLI 完整参考（Repo / Issue / PR / Actions） |
| `git-commit` | Github | 智能暂存与提交格式化 |
| `mcp-builder` | Anthropic | 构建高质量 MCP 服务器 |
| `react-best-practices` | Vercel | React/Next.js 性能优化指南 |

[02:38] **步骤 13：本教程直接用到的 skill**

![](frames/seg_0147_000013.jpg)

切到「已安装」视图：

- **`dogfood`** by Vercel：系统化地对 Web 应用进行内部试用和质量测试，输出含截图、复现视频和详细步骤的结构化缺陷报告
- **`byted-seedream-image-generate`** by Bytedance：使用火山引擎 Seedream 模型生成图像
- **`youtube-transcript`** by SamuelQZQ：Fetch transcripts from YouTube videos

*核心思路*：**命令 = prompt + skill 白名单**。命令负责说「做什么、输出在哪」，skill 负责真正跑代码。

---

## 九、Code 模式的网页端：云端 agent 测试 Web 应用

[02:56] **步骤 14：Web 端新建任务测网站**

![](frames/seg_0147_000010.jpg)

TRAE SOLO 的 **网页端**（`solo.trae.cn`）的 agent 跑在云端，不占本地资源也不占个人时间。作者打开新项目 `craft_platform`，调 `/dogfood 用这个技能帮我完整测试下这个网站：https://www.qzq.at/`。agent 自动执行：

```bash
mkdir -p ./dogfood-output/screenshots ./dogfood-output/videos
cp /data/user/skills/dogfood/templates/dogfood-report-template...
find / -name "agent-browser" 2>/dev/null | head -n 5
```

[02:59] **步骤 15：agent 真的打开了浏览器**

![](frames/seg_0147_000011.jpg)

右侧弹出一个 **浏览器** 窗口（云端无头浏览器），底部状态条显示 "Agent 操作中 · 我来接管"。agent 自动点击页面、填表、截屏，左侧日志里能看到它调了 `which agent-browser`、读 `issue-taxonomy.md`、最后 `导航到 https://www.qzq.at/`。

[03:21] **步骤 16：生成测试报告，右栏出现产物**

![](frames/seg_0147_000015.jpg)

右栏「上下文」出现 3 个文件产物：`report.md`、`issue-taxonomy.md`、`dogfood-report-template.md`。所有网站问题都被结构化了。

---

## 十、让 agent 把 Issue 提到 GitHub

[03:25] **步骤 17：让 AI 提 Issue**

![](frames/seg_0205_000001.jpg)

继续在同一个项目里输入：

```
请你把这里面提到的所有 issues，创建到这个 repo 的 issues 里面：SamuelQZQ/...
```

agent 自动识别到要用 `gh-cli` 技能。执行日志：

```
命令已执行: gh auth status
命令已执行: curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg ...
```

右栏进度条显示 **50%**。

**步骤 18：agent 卡在登录，主动停下来问你**

这一刻会弹出一个输入框：agent 说「我需要你帮我登录 GitHub」。这就是 **主动停下来提问** 的关键能力 —— 不是默默失败，而是把球踢回给人。帮它完成登录后，agent 自动继续运行，依次创建多个 Issue。

*为什么值得专门说这一幕*：传统 agent 要么装作看懂、要么静默崩溃；TRAE SOLO 的 agent 在 "需要人类决策时主动中断" 这条工程细节上做到了 —— **把人该做的判断留给人，不硬来**。

---

## 十一、为什么 TRAE 要做 MTC 模式？

[03:54] **总结**

![](frames/seg_0205_000007.jpg)

> **TRAE 是在把软件工程场景里已经跑通的 agentic 范式，迁移到更广泛知识工作者的场景，用更低门槛的界面，把高度产品化的智能体带给更多人。**

对普通用户的启示：

1. **把 AI 对话变成 workspace**：别再开一次性的 chat 窗口
2. **把常用任务写成命令**：三条命令就能覆盖 90% 的内容工作
3. **把能力装成 skill**：能用技能市场现成的就别自己 prompt
4. **让 agent 主动停下来**：需要人类判断时不硬猜，这是复利的前提

---

## 附录 A：完整三条命令模板

### 命令 1：摄取

```yaml
命令名称: 摄取
描述: 把外部 URL / 文件 / 音视频原样抓下来，归档到 /raw 并写 front-matter。
说明: |
  你负责把用户给出的外部资料抓取到本地 /raw 目录。流程：
  1. 识别输入类型（网页 / YouTube / PDF / 仓库 / 图片），选择合适的技能：
     - YouTube / Bilibili 视频：youtube-transcript
     - 网页：web-fetch 或抓取脚本
     - 图片：ocr 或多模态读图
  2. 抓取后写成 Markdown 文件，文件名格式：{YYYY-MM-DD}_{简短描述}.md
  3. 在文件头部生成 YAML front-matter，字段必须包括：
     title, source_name, source_url, author, published_at, captured_at,
     content_type, filename, tags（3-10 个中文标签）
  4. 若原文是英文，正文翻译为中文但保留原文链接和术语
  5. 落盘到 /raw 目录，不要污染 /wiki 或 /outputs
```

### 命令 2：消化

```yaml
命令名称: 消化
描述: 遍历 /raw 最近变动的文件，按 Atomic Notes 拆成原子笔记写入 /wiki。
说明: |
  你负责把 /raw 目录里最近修改的文件消化成 /wiki 里的原子笔记。流程：
  1. 检查 /raw 目录并选取最近修改的 1-3 个文件
  2. 读取原始文件内容，按 Atomic Notes 原则提取可复用的知识单元：
     - 每个原子笔记只讲一个概念
     - 命名格式：{概念名}-{简短描述}.md
     - 在正文用 [[wikilink]] 引用其他原子笔记，建立反向链接
  3. 为每条笔记补充 Properties：source_path, tags, 相关条目
  4. 若发现 /wiki 里已有相关条目，优先建立链接而不是重复创建
  5. 本次任务结束后用一两句话总结新增/修改了哪些条目
  不要硬编造，知识有缺口就指出来。
```

### 命令 3：输出-知识卡片

```yaml
命令名称: 输出-知识卡片
描述: 用于基于 /wiki 中已沉淀的知识生成一张知识卡片。
说明: |
  你负责围绕具体任务调用知识库内容进行输出，请先读取 /wiki 下相关条目，
  再生成一张知识卡片。输出的必须明确依赖了哪些知识条目；如果知识不足，
  要指出缺口和补充内容，而不是硬编造。若本次任务产生新的结构化记忆、
  问答或补充知识，请同步给出建议回写到 /wiki 的内容，让每次输出都能
  继续增强这个知识系统。

  知识卡片用 html 格式输出，模板使用如下 CSS 变量：
  --paper-2: #F7F2EA; --ink: #231F1C; --ink-light: #5F5751;
  --ink-dim: #8A7D71; --stone: #B1A79A; --line: #CFC4B8;
  --brick: #B23A36; --brick-dark: #8F3B31;
  --serif: 'DM Serif Display', 'Noto Serif SC', Georgia, serif;
  --sans: 'DM Sans', 'PingFang SC', system-ui, sans-serif;
  --mono: 'SF Mono', Menlo, monospace;
  画布尺寸 1600x900。
```

## 附录 B：技能清单

| Skill | 来源 | 本教程用途 |
| --- | --- | --- |
| `youtube-transcript` | SamuelQZQ | 摄取命令拉 YouTube 字幕 |
| `dogfood` | Vercel | 自动测试 Web 应用，生成缺陷报告 |
| `gh-cli` | Github | 把测试报告里的问题提成 GitHub Issue |
| `byted-seedream-image-generate` | Bytedance | 生成 PDF 文章里的配图 |
| `composition-patterns` | Vercel | React 组件架构参考 |
| `frontend-design` | Anthropic | 前端 UI 质量参考 |
| `git-commit` | Github | 智能暂存与提交 |
| `mcp-builder` | Anthropic | 构建 MCP 服务器 |
| `react-best-practices` | Vercel | React / Next.js 性能优化 |

## 一句话总结

**把 AI 从「对话窗口」升级为「workspace」，用 Compound Engineering 的四步循环（Plan → Work → Review → Compound）把每次任务都沉淀成可复用的系统资产。** TRAE SOLO 的 MTC 模式 + 自定义命令 + 技能市场，恰好提供了承载这套工作流的完整容器。三条命令（摄取 / 消化 / 输出）+ 一个本地 workspace，你就拥有一个越用越强的 AI 第二大脑。
