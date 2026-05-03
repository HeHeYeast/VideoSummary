"""Plan 12-02 backfill payload composer (one-shot, intentionally not committed).

Writes one JSON file per slug under /tmp/p12_payloads/<slug>.json.
Each JSON is the 8-field per-slug index payload Plan 12-02 needs to write
through `python -m agent.tools index write --slug X --from-stdin --force`.

This file is deliberately a literal dict-of-dicts (no clever inference) — the
Claude executor is the decider for every per-slug topics / keywords / tldr /
chapters per K5. Running this script once produces all 33 payload files; the
shell loop in the same plan invocation pipes each one through the CLI.
"""

import json
import os
from pathlib import Path

OUT = Path(os.environ.get("P12_OUT", "/tmp/p12_payloads"))
OUT.mkdir(parents=True, exist_ok=True)

PAYLOADS = {}

# ---------------- bimelona archives (AI 像素工具教程主线) ----------------

PAYLOADS["BV11JQBByE13"] = {
    "slug": "BV11JQBByE13",
    "title": "关于 AI 生成图片的抠图：场景与特效",
    "duration_s": 326.233,
    "mode": "replicate-guide",
    "topics": ["Pixel-Art", "AI-Art-Generation"],
    "keywords": ["双背景抠图法", "Add 模式特效抠图", "FrameRonin", "色度键扣图", "Photoshop"],
    "tldr_oneliner": "用「双背景对比」抠场景物件，用「Add 模式」抠特效——两条 AI 像素图抠图最稳的工艺路线",
    "chapters": [
        {"title": "一、双背景抠图法（场景/物件）", "start": 0, "excerpt": "让 AI 生成两张同布局但底色不同的图，比对底色差找 alpha mask"},
        {"title": "二、特效免抠图方案（Add 模式）", "start": 0, "excerpt": "AI 生成黑底特效后用 Add 混合模式直接合成，跳过抠图环节"},
        {"title": "总结", "start": 0, "excerpt": "两条路线的适用场景与组合用法"}
    ]
}

PAYLOADS["BV132wizyEEB"] = {
    "slug": "BV132wizyEEB",
    "title": "1 分钟搞定全套像素风游戏美术：AI 绘画 + 自动抠图全流程",
    "duration_s": 74.048,
    "mode": "replicate-guide",
    "topics": ["Pixel-Art", "AI-Art-Generation", "Godot"],
    "keywords": ["Gemini 像素生成", "topdown 俯视视角", "提示词约束", "色键抠图", "Godot 导入"],
    "tldr_oneliner": "用 Gemini + 提示词约束生成像素场景，迭代抠图后直接导入 Godot",
    "chapters": [
        {"title": "一、用 Gemini 生成像素风场景地图", "start": 6, "excerpt": "用提示词指定「像素场景画师」+ topdown 俯视 + 不出现人物三约束"},
        {"title": "二、迭代修改场景细节", "start": 15, "excerpt": "明确说「其余地方禁止改变」防止 AI 整图重画"},
        {"title": "三、提取场景中的物品素材", "start": 33, "excerpt": "要求 AI 用纯色背景排列物件方便后期抠图"},
        {"title": "四、生成空白场景背景", "start": 44, "excerpt": "让 AI 清除家具只留场景主体"},
        {"title": "五、去除 AI 水印", "start": 52, "excerpt": "Chrome 去水印插件一键处理"},
        {"title": "六、成果展示", "start": 62, "excerpt": "素材导入 Godot 引擎"}
    ]
}

PAYLOADS["BV15S9FBtEFm"] = {
    "slug": "BV15S9FBtEFm",
    "title": "零基础 30 天独立游戏开发挑战，我成功了吗？",
    "duration_s": 133.979,
    "mode": "extension-applications",
    "topics": ["Game-Dev", "Godot"],
    "keywords": ["30天独立开发", "AI 辅助游戏", "Godot", "复盘", "独立游戏"],
    "tldr_oneliner": "30 天 0 基础用 AI 工具复盘开发独立游戏的成果与坑——是踩坑展示而非教学",
    "chapters": [
        {"title": "已实现功能", "start": 0, "excerpt": "30 天里实际跑通的 AI + Godot 游戏功能集合"},
        {"title": "30 天总结", "start": 0, "excerpt": "复盘踩坑、流程、对独立开发者的建议"}
    ]
}

PAYLOADS["BV17WQuBJEzZ"] = {
    "slug": "BV17WQuBJEzZ",
    "title": "0 基础入门 AI 像素素材生成索引教程",
    "duration_s": 1105.799,
    "mode": "replicate-guide",
    "topics": ["Pixel-Art", "FrameRonin", "AI-Art-Generation"],
    "keywords": ["FrameRonin", "RPGMaker", "Rolling Flow", "视频转序列帧", "切图工具", "蓝图流程"],
    "tldr_oneliner": "FrameRonin 平台从 0 上手：低像素角色 / 多预设 / 视频转帧 / 切图 / 自定义蓝图全索引",
    "chapters": [
        {"title": "一、FrameRonin 平台概览", "start": 0, "excerpt": "平台模块全景：角色、场景、视频转帧、切图、蓝图"},
        {"title": "二、核心流程：低像素角色生成（RPGMaker）", "start": 0, "excerpt": "RPGMaker 风格低像素角色 1 分钟生成流程"},
        {"title": "三、多版本预设与自定义流程（Rolling Flow）", "start": 0, "excerpt": "把多个步骤串成 Rolling Flow 一键跑"},
        {"title": "四、场景生成学习路径", "start": 0, "excerpt": "从单图到大地图的进阶顺序"},
        {"title": "五、视频转序列帧", "start": 0, "excerpt": "把视频导出成序列帧素材"},
        {"title": "六、切图工具详解", "start": 0, "excerpt": "切图 + 微调像素细节"},
        {"title": "七、像素处理辅助功能", "start": 0, "excerpt": "颜色调整、描边、对齐"},
        {"title": "八、自定义蓝图流程（Rolling Flow）", "start": 0, "excerpt": "自定义节点串联生成定制工作流"}
    ]
}

PAYLOADS["BV1C9QCBdE1U"] = {
    "slug": "BV1C9QCBdE1U",
    "title": "Godot 4 伤害数字生成器：暴击变色 + 随机漂浮 + Tween 动画",
    "duration_s": 520.0,
    "mode": "replicate-guide",
    "topics": ["Godot", "Game-Dev"],
    "keywords": ["DamageNumberSpawner", "GDScript", "Tween 动画", "Label 节点", "暴击变色", "导出变量"],
    "tldr_oneliner": "Godot 4 用自定义节点 + Tween 实现可复用的暴击伤害数字飘字组件",
    "chapters": [
        {"title": "1. 创建自定义节点脚本", "start": 0, "excerpt": "用 GDScript 写 DamageNumberSpawner 自定义节点"},
        {"title": "2. 声明导出变量", "start": 0, "excerpt": "用 @export 让 inspector 可调字体颜色 + 暴击颜色"},
        {"title": "3. 定义 spawn_label 函数", "start": 0, "excerpt": "在指定位置实例化 Label 节点显示伤害数字"},
        {"title": "4. 创建 Label 并设置属性", "start": 0, "excerpt": "动态创建 Label 节点 + 设置 text / color / font_size"},
        {"title": "5. 暴击变色", "start": 0, "excerpt": "根据 is_critical 参数切换 modulate 颜色"},
        {"title": "9. Tween 动画：上浮 + 放大 + 淡出", "start": 0, "excerpt": "Tween 串联 position / scale / modulate.a 三段动画"}
    ]
}

PAYLOADS["BV1EWwXzvE23"] = {
    "slug": "BV1EWwXzvE23",
    "title": "更大的像素化场景生成办法（南向扩图迭代）",
    "duration_s": 259.298,
    "mode": "replicate-guide",
    "topics": ["Pixel-Art", "AI-Art-Generation", "Godot"],
    "keywords": ["像素场景生成", "Gemini Gem", "南向扩图", "提示词关键词", "Godot 拼图"],
    "tldr_oneliner": "用 Gemini Gem 反复向南扩图，把单屏地图扩成连续大地图后在 Godot 拼装",
    "chapters": [
        {"title": "第二步：打开 Gemini「像素场景生成 v1.1」Gem", "start": 0, "excerpt": "调用预设的 Gem 智能体"},
        {"title": "第三步：生成初始场景", "start": 0, "excerpt": "标准提示词生成首屏"},
        {"title": "第四步：用关键提示词向南扩展地图", "start": 0, "excerpt": "用「在南方继续延伸」类提示词追加屏幕"},
        {"title": "第五步：反复迭代，持续向南扩展", "start": 0, "excerpt": "多轮迭代逐屏扩"},
        {"title": "第六步：在 Godot 中组装地图", "start": 0, "excerpt": "把多张图导入 Godot 拼接成连续大地图"}
    ]
}

PAYLOADS["BV1HG9JBsEPK"] = {
    "slug": "BV1HG9JBsEPK",
    "title": "AI 辅助 tilemap 无限随机地图生成（tile47/blob 算法实战）",
    "duration_s": 640.466,
    "mode": "replicate-guide",
    "topics": ["TileMap", "Procedural-Generation", "Pixel-Art", "Godot"],
    "keywords": ["tile47 算法", "blob 邻接", "FrameRonin", "mask-to-index", "随机地图生成", "tilemap"],
    "tldr_oneliner": "tile47/blob 算法 47 种邻接情况一次讲透，配 FrameRonin 工具生成可换风格的随机大地图",
    "chapters": [
        {"title": "一、核心概念：blob/tile47 算法的 47 种邻接情况", "start": 0, "excerpt": "8 邻接合并出的 47 种独立 tile 形态"},
        {"title": "二、工具本体：FrameRonin 在线无限地图生成器", "start": 0, "excerpt": "在线工具生成无限大随机 tilemap"},
        {"title": "四、关键步骤：让 AI 帮你算 mask→tile 的编码", "start": 0, "excerpt": "用 ChatGPT 算邻接 mask 到 tile index 的对照表"},
        {"title": "五、AI 生成新风格的 tilemap 图块", "start": 0, "excerpt": "用 AI 重画 tile 图块换主题风格"},
        {"title": "六、风格替换 + 元素提取", "start": 0, "excerpt": "把生成的图块换皮"},
        {"title": "七、装配 + 延展玩法", "start": 0, "excerpt": "成品生成器装配后做村庄/副本扩展"}
    ]
}

PAYLOADS["BV1Kk9MBNEgV"] = {
    "slug": "BV1Kk9MBNEgV",
    "title": "AI 均分重绘法生成超高清古风主城",
    "duration_s": 258.298,
    "mode": "replicate-guide",
    "topics": ["AI-Art-Generation", "Pixel-Art"],
    "keywords": ["均分重绘", "古风主城", "高分辨率", "瓦片分块", "AI 重绘"],
    "tldr_oneliner": "把低分场景切成均匀网格分别让 AI 重绘高分版本再拼回——破解 AI 直出分辨率上限",
    "chapters": [
        {"title": "一、问题：低分辨率不够用", "start": 0, "excerpt": "AI 直出大场景细节不够"},
        {"title": "二、均分重绘法完整流程", "start": 0, "excerpt": "网格切片 + 单独重绘 + 边缘缝合"},
        {"title": "三、最终效果对比", "start": 0, "excerpt": "前后清晰度对比"}
    ]
}

PAYLOADS["BV1RA9uBSEh3"] = {
    "slug": "BV1RA9uBSEh3",
    "title": "AI 做游戏又双叒叕进化了：写代码 + 像素 + 平衡 + UI",
    "duration_s": 125.108,
    "mode": "extension-applications",
    "topics": ["Game-Dev", "Codex", "AI-Tooling"],
    "keywords": ["Codex Demo", "Skill 平衡", "像素素材", "全自动管线", "AI 玩自己的游戏"],
    "tldr_oneliner": "AI 现在能跑完「写 Demo → 自调平衡 → 生成像素 → 拼 UI」全管线",
    "chapters": [
        {"title": "管线概览", "start": 0, "excerpt": "AI 全栈做游戏的 4 个 Skill 节点"},
        {"title": "第一步：用 Codex 生成 Demo", "start": 0, "excerpt": "Codex 直接产出可玩 Demo"},
        {"title": "第二步：策划 Skill — AI 自己玩、自己调", "start": 0, "excerpt": "AI 跑测试帧再回填平衡参数"},
        {"title": "第三步：美术 Skill — 像素素材自动生成", "start": 0, "excerpt": "美术 Skill 调用图模型自动出素材"},
        {"title": "第四步：全自动管线", "start": 0, "excerpt": "4 个 Skill 串成自动管线"}
    ]
}

PAYLOADS["BV1RXdZBtEKN"] = {
    "slug": "BV1RXdZBtEKN",
    "title": "场景元素的提取及处理：解决大地图元素与人物前后关系",
    "duration_s": 327.935,
    "mode": "replicate-guide",
    "topics": ["Pixel-Art", "FrameRonin", "Godot"],
    "keywords": ["双背景分离", "FrameRonin 抠图", "RoninPro 切图", "硬边描边", "前后遮挡关系"],
    "tldr_oneliner": "用双背景生成 + RoninPro 切图把场景元素抠成独立物件，解决大地图与角色的前后遮挡问题",
    "chapters": [
        {"title": "一、生成「双背景」分离图", "start": 0, "excerpt": "用 AI 生成同布局不同底色版本"},
        {"title": "二、FrameRonin 双背景扣图", "start": 0, "excerpt": "用 FrameRonin 自动比对底色出 mask"},
        {"title": "三、RoninPro 零散切图：批量分离", "start": 0, "excerpt": "RoninPro 批量按物件切片"},
        {"title": "四、低像素元素 + 完美像素", "start": 0, "excerpt": "处理低像素与硬像素混排"},
        {"title": "五、PS 后处理：硬边描边", "start": 0, "excerpt": "Photoshop 硬边描边补完"},
        {"title": "六、把元素放回场景（Godot 侧）", "start": 0, "excerpt": "Godot 中分层放置元素解决前后遮挡"}
    ]
}

PAYLOADS["BV1SPB6BxE2t"] = {
    "slug": "BV1SPB6BxE2t",
    "title": "Nano Banana 攻略：大量制作高质量游戏美术资源",
    "duration_s": 2728.907,
    "mode": "replicate-guide",
    "topics": ["Nano-Banana", "AI-Art-Generation", "Game-Dev"],
    "keywords": ["Nano Banana", "装备图标批量", "游戏场景设计", "角色设计", "AI 美术管线"],
    "tldr_oneliner": "Nano Banana 工具完整攻略：装备图标 / 场景 / 角色三大类游戏美术资源批量产出",
    "chapters": [
        {"title": "教程总览", "start": 0, "excerpt": "Nano Banana 工具与三大资源类型概览"},
        {"title": "一、装备图标批量生成", "start": 0, "excerpt": "批量生成风格统一的装备图标"},
        {"title": "二、游戏场景设计", "start": 0, "excerpt": "场景生成 + 风格控制"},
        {"title": "三、角色设计", "start": 0, "excerpt": "角色立绘 + 一致性控制"},
        {"title": "核心技巧总结", "start": 0, "excerpt": "三大类型共通的提示词与流程经验"}
    ]
}

PAYLOADS["BV1TrP6zHETD"] = {
    "slug": "BV1TrP6zHETD",
    "title": "Godot 4.7 重磅更新：新功能介绍",
    "duration_s": 610.337,
    "mode": "extension-applications",
    "topics": ["Godot", "Game-Dev"],
    "keywords": ["Godot 4.7", "VirtualJoystick", "Path3D 吸附", "DrawableTexture", "GDScript", "动画轨道"],
    "tldr_oneliner": "Godot 4.7 9 项新功能横向罗列：编辑器 / 虚拟摇杆 / 3D 路径 / 动态纹理 / GDScript 调试",
    "chapters": [
        {"title": "1. 编辑器：属性组复制粘贴", "start": 0, "excerpt": "属性组级别的 copy / paste"},
        {"title": "2. 内置虚拟摇杆 VirtualJoystick", "start": 0, "excerpt": "无需插件直接用的虚拟摇杆"},
        {"title": "3. Path3D 吸附到碰撞体", "start": 0, "excerpt": "Path3D 自动贴合 collision"},
        {"title": "4. 可绘制纹理 DrawableTexture", "start": 0, "excerpt": "运行时可写入的纹理"},
        {"title": "5. GDScript 远程检查器改进", "start": 0, "excerpt": "运行时变量调试改进"},
        {"title": "8. 动画轨道编辑器：折叠分组", "start": 0, "excerpt": "动画轨道可折叠分组"}
    ]
}

PAYLOADS["BV1W3PyztE4q"] = {
    "slug": "BV1W3PyztE4q",
    "title": "超简单 两分钟就能学会的 AI 游戏开发方案 | 30 天计划第四天",
    "duration_s": 133.235,
    "mode": "replicate-guide",
    "topics": ["MCP", "Godot", "AI-Tooling"],
    "keywords": ["godot-mcp", "MCP 安装", "AI 修 Bug", "Cursor", "Godot 集成"],
    "tldr_oneliner": "godot-mcp 安装 + 用 AI 直接在 Godot 编辑器里修 Bug 的最小可用流程",
    "chapters": [
        {"title": "godot-mcp 安装教程", "start": 0, "excerpt": "MCP 协议下 godot-mcp 的安装步骤"},
        {"title": "使用演示：AI 修 Bug", "start": 0, "excerpt": "AI 通过 MCP 直接读项目文件修 Bug"},
        {"title": "总结", "start": 0, "excerpt": "适用场景与限制"}
    ]
}

PAYLOADS["BV1YTQQBcEWs"] = {
    "slug": "BV1YTQQBcEWs",
    "title": "当游戏 NPC 拥有了自主意识，第 20 天我给游戏接入了 AI",
    "duration_s": 71.447,
    "mode": "replicate-guide",
    "topics": ["Game-AI-NPC", "Godot", "Game-Dev"],
    "keywords": ["NPC 自主意识", "Godot AI 接入", "对话系统", "游戏 AI", "30天计划"],
    "tldr_oneliner": "给 Godot 游戏 NPC 接入 LLM 实现自主意识对话——30 天独立开发挑战 day 20 节点演示",
    "chapters": [
        {"title": "核心功能展示", "start": 0, "excerpt": "NPC 接入 LLM 后的对话与行为示例"},
        {"title": "总结", "start": 0, "excerpt": "技术要点与下一步计划"}
    ]
}

PAYLOADS["BV1dQPezJEmG"] = {
    "slug": "BV1dQPezJEmG",
    "title": "AI 生成像素帧序列人物再更新",
    "duration_s": 345.466,
    "mode": "replicate-guide",
    "topics": ["Sprite-Animation", "Pixel-Art", "AI-Art-Generation"],
    "keywords": ["像素帧序列", "Photoshop 像素化", "边缘处理", "Gemini 帧生成"],
    "tldr_oneliner": "新版本生成像素帧序列后用 Photoshop 边缘像素化处理一次性补完角色动画",
    "chapters": [
        {"title": "一、新版本功能介绍", "start": 0, "excerpt": "最新版的帧序列生成能力"},
        {"title": "二、PS 边缘像素化处理教程", "start": 0, "excerpt": "Photoshop 后处理统一像素边缘"}
    ]
}

PAYLOADS["BV1dUDLBaEeb"] = {
    "slug": "BV1dUDLBaEeb",
    "title": "复刻星露谷同款矿洞：从 0 学习程序化生成地图",
    "duration_s": 71.006,
    "mode": "concept-explanation",
    "topics": ["Procedural-Generation", "TileMap", "Game-Dev", "Godot"],
    "keywords": ["程序化生成", "矿洞地图", "星露谷", "迭代算法", "随机种子"],
    "tldr_oneliner": "用最简单的迭代算法复刻星露谷矿洞——程序化地图生成的最小心智模型",
    "chapters": [
        {"title": "算法流程", "start": 0, "excerpt": "迭代生成矿洞房间 + 走廊的步骤"},
        {"title": "核心思路", "start": 0, "excerpt": "为什么迭代法比 noise 在矿洞场景更适合"}
    ]
}

PAYLOADS["BV1f1Q2BfEoN"] = {
    "slug": "BV1f1Q2BfEoN",
    "title": "完全不会美术，0 成本用 AI 也能做出丝滑的角色动画",
    "duration_s": 92.345,
    "mode": "replicate-guide",
    "topics": ["Sprite-Animation", "Pixel-Art", "AI-Art-Generation"],
    "keywords": ["角色动画", "AI 帧序列", "丝滑动画", "0 成本流程"],
    "tldr_oneliner": "0 美术基础 + 0 成本用 AI 出整套丝滑角色动画的工作流",
    "chapters": [
        {"title": "完整工作流", "start": 0, "excerpt": "AI 生成关键帧 + 自动补帧 + 后处理全流程"},
        {"title": "流程总结", "start": 0, "excerpt": "工具链与坑位"}
    ]
}

PAYLOADS["BV1f2WZzzEMp"] = {
    "slug": "BV1f2WZzzEMp",
    "title": "香蕉自动化生成素材：并发生成、自动命名、自动抠图",
    "duration_s": 177.237,
    "mode": "replicate-guide",
    "topics": ["Nano-Banana", "ComfyUI", "AI-Art-Generation"],
    "keywords": ["Nano Banana", "ComfyUI 工作流", "并发生成", "自动命名", "绿幕抠图", "智能保存"],
    "tldr_oneliner": "ComfyUI 工作流：并发跑香蕉模型 + 命名细化 + 高清放大 + 绿幕抠图全打包",
    "chapters": [
        {"title": "1. 工作流全貌", "start": 0, "excerpt": "ComfyUI 节点图概览"},
        {"title": "2. 命名细化版节点详解", "start": 0, "excerpt": "细化命名节点的逐字段讲解"},
        {"title": "4. 用相对路径自动分文件夹", "start": 0, "excerpt": "相对路径让 AI 自分类输出"},
        {"title": "6. 并发与保存模式设置", "start": 0, "excerpt": "并发生成提速 + 自定义保存策略"},
        {"title": "7. 高清放大流程", "start": 0, "excerpt": "下游连超分节点"},
        {"title": "8. 绿幕抠图流程", "start": 0, "excerpt": "节点链自动绿幕抠图输出 PNG"}
    ]
}

PAYLOADS["BV1fLoKBREAN"] = {
    "slug": "BV1fLoKBREAN",
    "title": "从零开始的 Godot 游戏开发 #01：引擎安装与瓦片系统基础",
    "duration_s": 1059.264,
    "mode": "replicate-guide",
    "topics": ["Godot", "TileMap", "Game-Dev"],
    "keywords": ["Godot 安装", "瓦片系统", "TileMap", "纹理过滤", "动态瓦片", "Camera2D"],
    "tldr_oneliner": "从零基础到能用 Godot TileMap 画出可走的 2D 场景的完整第一课",
    "chapters": [
        {"title": "一、Godot 安装与项目创建", "start": 0, "excerpt": "下载 Godot + 新建项目"},
        {"title": "二、素材导入与纹理过滤", "start": 0, "excerpt": "禁用 filter 保留像素硬边"},
        {"title": "三、瓦片系统：静态瓦片绘制", "start": 0, "excerpt": "TileMap + TileSet 基础绘制"},
        {"title": "四、瓦片系统：动态瓦片（4 帧动画）", "start": 0, "excerpt": "TileSet 内的动画瓦片配置"},
        {"title": "五、装饰瓦片层：处理 16×32 双格子瓦片", "start": 0, "excerpt": "占两格的高瓦片配置"},
        {"title": "六、Camera2D：摄像机与缩放", "start": 0, "excerpt": "相机跟随 + 缩放参数"},
        {"title": "七、伸缩模式与背景色", "start": 0, "excerpt": "Stretch Mode + 背景色"}
    ]
}

PAYLOADS["BV1hUAMzYEc8"] = {
    "slug": "BV1hUAMzYEc8",
    "title": "利用蓝图批量处理像素素材",
    "duration_s": 173.599,
    "mode": "replicate-guide",
    "topics": ["FrameRonin", "Pixel-Art"],
    "keywords": ["蓝图节点", "批量处理", "FrameRonin", "工作流保存", "预设节点"],
    "tldr_oneliner": "FrameRonin 蓝图把多个像素处理步骤串成可复用工作流批量执行",
    "chapters": [
        {"title": "一、为什么需要蓝图", "start": 0, "excerpt": "重复手动操作 → 蓝图节点链"},
        {"title": "二、蓝图操作演示", "start": 0, "excerpt": "拖节点连线跑批量"},
        {"title": "三、可用预设节点列表", "start": 0, "excerpt": "FrameRonin 内置预设节点"},
        {"title": "四、工作流保存与加载", "start": 0, "excerpt": "蓝图导出 / 复用"}
    ]
}

PAYLOADS["BV1jXXaBQE1R"] = {
    "slug": "BV1jXXaBQE1R",
    "title": "在清华读研半年，我做了个开源游戏引擎",
    "duration_s": 900.028,
    "mode": "concept-explanation",
    "topics": ["Custom-Engine", "Game-Dev"],
    "keywords": ["开源引擎", "ECS", "渲染管线", "技术架构", "引擎自研"],
    "tldr_oneliner": "清华研究生 6 个月写的开源游戏引擎：架构选型、ECS、渲染管线的设计判断",
    "chapters": [
        {"title": "背景：为什么做这个引擎", "start": 0, "excerpt": "选择自研引擎而非用现成的理由"},
        {"title": "技术架构总览", "start": 0, "excerpt": "ECS / 渲染管线 / 模块边界"},
        {"title": "核心特性详解", "start": 0, "excerpt": "ECS / 序列化 / 编辑器 / 资产系统"},
        {"title": "当前局限 & 未来计划", "start": 0, "excerpt": "目前还缺什么、下一步要补什么"},
        {"title": "核心理念总结", "start": 0, "excerpt": "做引擎要不要重新发明轮子"}
    ]
}

PAYLOADS["BV1p2c6zTEn2"] = {
    "slug": "BV1p2c6zTEn2",
    "title": "AI 生成像素帧序列人物再再更新 V4",
    "duration_s": 203.466,
    "mode": "replicate-guide",
    "topics": ["Sprite-Animation", "Pixel-Art", "Godot"],
    "keywords": ["V4 帧序列", "Gemini 帧生成", "PS 像素化", "Godot 序列帧", "动作展示"],
    "tldr_oneliner": "V4 版本帧序列：Gemini 生成 + PS 像素化 + Godot 序列帧导入完整链路",
    "chapters": [
        {"title": "一、V4 版本动作展示", "start": 0, "excerpt": "V4 新版本支持的动作集合"},
        {"title": "二、Gemini 生成流程", "start": 0, "excerpt": "Gemini 生成关键帧的提示词"},
        {"title": "三、PS 像素化处理", "start": 0, "excerpt": "Photoshop 后处理统一像素感"},
        {"title": "四、Godot 中使用", "start": 0, "excerpt": "导入 Godot 配置 AnimatedSprite"}
    ]
}

PAYLOADS["BV1qQPeznE5H"] = {
    "slug": "BV1qQPeznE5H",
    "title": "Godot 像素角色跟随功能展示及场景素材生成",
    "duration_s": 271.166,
    "mode": "replicate-guide",
    "topics": ["Godot", "Pixel-Art", "Sprite-Animation"],
    "keywords": ["角色跟随", "色度键抠图", "扩图缩图", "场景建筑分层", "Godot"],
    "tldr_oneliner": "Godot 像素角色跟随系统 + 用色度键抠图把建筑分层做大场景",
    "chapters": [
        {"title": "一、Godot 角色跟随系统演示", "start": 0, "excerpt": "Camera + 跟随脚本基础"},
        {"title": "二、场景建筑分层（色度键抠图）", "start": 0, "excerpt": "用色度键把建筑切成多层"},
        {"title": "三、扩图与缩图功能", "start": 0, "excerpt": "AI 工具扩图 / 缩图"},
        {"title": "总结", "start": 0, "excerpt": "工具链复盘"}
    ]
}

PAYLOADS["BV1rsd7BsEnA"] = {
    "slug": "BV1rsd7BsEnA",
    "title": "绝美画风 LoRA 模型保姆级教学：打标 + 上机实操",
    "duration_s": 2029.504,
    "mode": "replicate-guide",
    "topics": ["LoRA", "AI-Art-Generation"],
    "keywords": ["LoRA 训练", "AI-Toolkit", "打标", "触发词", "checkpoint", "云端训练", "仙宫云"],
    "tldr_oneliner": "LoRA 模型从打标到本地训练再到云端炼丹的完整保姆级实操流程",
    "chapters": [
        {"title": "第一部分：打标的核心理念", "start": 58, "excerpt": "概念矛盾 vs 概念玻璃 / 以用定打的判断标准"},
        {"title": "第二部分：触发词设计", "start": 330, "excerpt": "触发词的选取原则与命名规范"},
        {"title": "第三部分：数据准备", "start": 523, "excerpt": "训练集图片清洗与目录结构"},
        {"title": "第四部分：AI 自动打标", "start": 756, "excerpt": "Gemini / WD14 自动标注流程"},
        {"title": "第五部分：AI-Toolkit 一键整合包 + 本地训练", "start": 930, "excerpt": "本地 AI-Toolkit 跑 LoRA 训练"},
        {"title": "第六部分：训练参数 + 验证集", "start": 1320, "excerpt": "学习率 / 步数 / 验证集设置"},
        {"title": "第七部分：云端训练（仙宫云）", "start": 1620, "excerpt": "用仙宫云 GPU 训练加速"},
        {"title": "第八部分：评分挑选最佳 checkpoint", "start": 1800, "excerpt": "多 checkpoint 横评打分挑选"}
    ]
}

PAYLOADS["BV1s6rDBpEvo"] = {
    "slug": "BV1s6rDBpEvo",
    "title": "2D 游戏中的雨天效果 DEV LOG.02",
    "duration_s": 126.85,
    "mode": "replicate-guide",
    "topics": ["Godot", "Game-Dev"],
    "keywords": ["雨滴系统", "SubViewport", "MultiMesh", "屏幕纹理", "UV 扭曲", "造波"],
    "tldr_oneliner": "Godot 2D 雨天：雨滴 + 积水 + 水波纹 + 倒影 + 反射扰动 + 折射 6 个层叠效果",
    "chapters": [
        {"title": "一、雨滴系统", "start": 0, "excerpt": "粒子模拟雨滴下落"},
        {"title": "二、积水形状：噪波 + Step 裁切", "start": 0, "excerpt": "用 noise + step 函数生成积水形状"},
        {"title": "三、雨水落地的水波纹（SubViewport）", "start": 0, "excerpt": "SubViewport 渲染水波涟漪"},
        {"title": "四、场景倒影：MultiMesh 翻转", "start": 0, "excerpt": "MultiMesh 翻转实现倒影"},
        {"title": "五、反射扰动：用造波打乱倒影", "start": 0, "excerpt": "在倒影上叠造波扰动"},
        {"title": "六、地面折射：屏幕纹理 + UV 扭曲", "start": 0, "excerpt": "屏幕纹理 + UV 扭曲做湿地折射"}
    ]
}

PAYLOADS["BV1sXcqziE4W"] = {
    "slug": "BV1sXcqziE4W",
    "title": "12 小时极限开发，奴役 AI——分权制衡多 Agent 架构实战",
    "duration_s": 755.925,
    "mode": "extension-applications",
    "topics": ["AI-Tooling", "Game-Dev", "Claude-Code"],
    "keywords": ["GLM-5", "多 Agent 架构", "分权制衡", "Midjourney", "Suno", "极限开发", "逃离千禧年"],
    "tldr_oneliner": "12 小时极限开发：GLM-5 + 分权多 Agent + Midjourney + Suno 凑出完整独立游戏管线",
    "chapters": [
        {"title": "1. 成品展示：逃离千禧年", "start": 0, "excerpt": "12 小时做出来的成品游戏演示"},
        {"title": "2. 关键决策：为什么选 GLM-5 而不是 Claude", "start": 0, "excerpt": "GLM-5 在极限开发场景的取舍"},
        {"title": "3. 核心方法论：分权制衡的多 Agent 架构", "start": 0, "excerpt": "多 Agent 互相校验避免一家独大"},
        {"title": "4. 实战案例一：华容道背包系统", "start": 0, "excerpt": "华容道背包功能从设计到实现"},
        {"title": "5. 实战案例二：CRT 滤镜 Bug 的排查与修复", "start": 0, "excerpt": "CRT shader bug 多 Agent 协作排查"},
        {"title": "6. 美术管线：Midjourney 多图训练 + Python 批处理", "start": 0, "excerpt": "Midjourney 训练自定义风格 + 批处理"},
        {"title": "7. 音乐管线：Suno 生成 + GLM-5 写 Prompt", "start": 0, "excerpt": "Suno 出 BGM + LLM 写音乐 prompt"}
    ]
}

PAYLOADS["BV1wu9MBZEbU"] = {
    "slug": "BV1wu9MBZEbU",
    "title": "如何打造自己的 Gem 智能体（或者拷贝别人的）",
    "duration_s": 199.866,
    "mode": "replicate-guide",
    "topics": ["AI-Tooling"],
    "keywords": ["Gem 智能体", "Gemini", "反向推导指令", "自定义智能体", "智能体复制"],
    "tldr_oneliner": "Gemini Gem 智能体：自建 / 反推别人的指令 / 复制三种打造方式",
    "chapters": [
        {"title": "一、创建自己的 Gem", "start": 0, "excerpt": "Gemini 后台创建自定义 Gem"},
        {"title": "二、反向推导别人的 Gem 指令", "start": 0, "excerpt": "用提示词让目标 Gem 自报指令"},
        {"title": "三、复制别人的 Gem", "start": 0, "excerpt": "把推导出来的指令灌进自己的 Gem"}
    ]
}

PAYLOADS["BV1x31TYUEbc"] = {
    "slug": "BV1x31TYUEbc",
    "title": "Godot 如何构建完整的 2D 农场游戏（8 小时教程系列）",
    "duration_s": 30500.652,
    "mode": "replicate-guide",
    "topics": ["Godot", "Game-Dev", "TileMap"],
    "keywords": ["农场游戏", "Godot 完整项目", "8 小时教程", "全流程", "2D 游戏"],
    "tldr_oneliner": "Godot 从 0 做出完整 2D 农场游戏的 8 小时全流程教程",
    "chapters": [
        {"title": "教程大纲", "start": 0, "excerpt": "8 小时课程的章节地图"},
        {"title": "核心技术要点", "start": 0, "excerpt": "本系列覆盖的关键 Godot 技术点"},
        {"title": "素材与资源", "start": 0, "excerpt": "需要下载的素材包与外部资源"}
    ]
}

# ---------------- douyin archives ----------------

PAYLOADS["douyin_ai_kb"] = {
    "slug": "douyin_ai_kb",
    "title": "复刻 Karpathy 的个人知识库管理范式：LLM Wiki",
    "duration_s": 122.346,
    "mode": "concept-explanation",
    "topics": ["LLM-Wiki", "LLM-Concepts", "AI-Tooling"],
    "keywords": ["LLM Wiki", "Karpathy", "个人知识库", "Atomic Notes", "raw/wiki/lab 三文件夹"],
    "tldr_oneliner": "Karpathy LLM Wiki 范式中文复刻：raw/wiki/lab 三文件夹 + LLM 当编译器的最小落地",
    "chapters": [
        {"title": "为什么你的收藏夹没救了", "start": 0, "excerpt": "碎片化阅读只产生「学到了」的虚假快感"},
        {"title": "Andrej Karpathy 给出的答案", "start": 0, "excerpt": "Karpathy 75 行 gist 提出 LLM Wiki 范式"},
        {"title": "核心理念：编译，而非存储", "start": 0, "excerpt": "Knowledge = Σ(Fragments) × Compiler 公式"},
        {"title": "IDE 实操：三步落地", "start": 0, "excerpt": "raw/wiki/lab 三文件夹 + Schema 文件 + LLM 当 wiki 管理员"},
        {"title": "为什么要费劲建立体系", "start": 0, "excerpt": "对比 RAG：体系 + 编译比临时检索更有效"},
        {"title": "行动清单：从今天第一篇 Raw 开始", "start": 0, "excerpt": "今天就动手的最小可行流程"}
    ]
}

PAYLOADS["douyin_claude_code_hooks"] = {
    "slug": "douyin_claude_code_hooks",
    "title": "Claude Code 系列教程第 6 期：Hooks 事件驱动自动化",
    "duration_s": 68.453,
    "mode": "extension-applications",
    "topics": ["Claude-Code", "AI-Tooling"],
    "keywords": ["Claude Code Hooks", "PostToolUse", "事件驱动", "Command Hook", "Prompt Hook", "HTTP Hook", "Agent Hook"],
    "tldr_oneliner": "Claude Code Hooks：4 类 Hook × 4 类事件 → 把 lint/扫描/通知 挂在事件上而非意志上",
    "chapters": [
        {"title": "什么是 Hooks", "start": 0, "excerpt": "事件驱动自动化的核心概念"},
        {"title": "四种 Hook 类型", "start": 10, "excerpt": "Command / Prompt / HTTP / Agent 4 类工具的边界"},
        {"title": "四种触发事件", "start": 28, "excerpt": "PostToolUse / Stop / 等 4 个事件的语义"},
        {"title": "实战案例：写完文件自动扫描敏感信息", "start": 50, "excerpt": "Command + PostToolUse 配 scan-secrets.sh 的最小 JSON 配置"},
        {"title": "更多实用思路", "start": 60, "excerpt": "其他 hook 组合的实用场景"}
    ]
}

PAYLOADS["douyin_karpathy_llm_wiki"] = {
    "slug": "douyin_karpathy_llm_wiki",
    "title": "Karpathy 又被吹爆，但这次可能真不是炒作",
    "duration_s": 242.027,
    "mode": "interview-distillation",
    "topics": ["LLM-Wiki", "LLM-Concepts", "RAG"],
    "keywords": ["Karpathy", "LLM Wiki", "RAG", "Memex", "Vannevar Bush", "命名的力量", "三层结构"],
    "tldr_oneliner": "UP 主对 Karpathy LLM Wiki gist 的判断：方法不新，命名才是真正的爆点",
    "chapters": [
        {"title": "[00:00] 一个 75 行 gist 为什么突然炸了", "start": 0, "excerpt": "UP 主开场：方法不新，命名才新"},
        {"title": "[00:28] RAG 的顺序搞反了：三层结构才是正解", "start": 28, "excerpt": "三层结构 Raw / Wiki / Schema 的权限边界"},
        {"title": "[00:57] 三个动作：Ingest · Query · Lint", "start": 57, "excerpt": "Ingest 写入式更新 / Query 读编译产物 / Lint 体检"},
        {"title": "[01:25] 最狠的比方：新员工 vs 图书管理员", "start": 85, "excerpt": "RAG = 新员工现查现忘；LLM Wiki = 图书管理员持续整理"},
        {"title": "[02:10] 整个 gist 最炸的一句", "start": 130, "excerpt": "Schema 是让 LLM 成为 disciplined wiki maintainer 的关键"},
        {"title": "[02:23] 但不能只听 Karpathy：反方三连击", "start": 143, "excerpt": "@kubb / @kepano / B 站本土质疑三连"},
        {"title": "[03:21] 收口：1945 年那个问题，LLM 终于能回答了", "start": 201, "excerpt": "Vannevar Bush 的 Memex 80 年缺口被 LLM 填上"}
    ]
}

PAYLOADS["douyin_trae_ai"] = {
    "slug": "douyin_trae_ai",
    "title": "搭建全网千万收藏的 AI 第二大脑：TRAE SOLO 实战教程",
    "duration_s": 251.936,
    "mode": "replicate-guide",
    "topics": ["TRAE-SOLO", "Compound-Engineering", "AI-Tooling", "LLM-Wiki"],
    "keywords": ["TRAE SOLO", "Compound Engineering", "MTC 模式", "摄取/消化/输出", "LLM Wiki", "命令面板"],
    "tldr_oneliner": "TRAE SOLO 桌面端搭出「摄取 → 消化 → 输出」AI 第二大脑工作流的实战教程",
    "chapters": [
        {"title": "一、先理解核心理念：Compound Engineering", "start": 5, "excerpt": "Plan → Work → Review → Compound 四步循环"},
        {"title": "二、看清目标：LLM 维护的个人知识库长什么样", "start": 0, "excerpt": "目标产物：raw/wiki/outputs 三层"},
        {"title": "三、进入 TRAE SOLO 桌面端：打开命令面板", "start": 88, "excerpt": "MTC 模式 + 本地 workspace + 命令面板"},
        {"title": "四、创建三条自定义命令", "start": 103, "excerpt": "摄取 / 消化 / 输出三条命令的 prompt 模板"},
        {"title": "五、演示「摄取」命令：把 YouTube 视频扒成本地笔记", "start": 0, "excerpt": "youtube-transcript skill + 归档到 /raw"},
        {"title": "六、演示「消化」命令：生成原子笔记 + 自动建图", "start": 0, "excerpt": "raw → wiki 的 Atomic Notes 自动化"},
        {"title": "七、切换 Code 模式：用「输出」命令生成 HTML 知识卡片", "start": 0, "excerpt": "Code 模式生成可分享 HTML 知识卡片"}
    ]
}

PAYLOADS["douyin_zidan_bojirouxunlian"] = {
    "slug": "douyin_zidan_bojirouxunlian",
    "title": "你的运动形式决定了你能否练出薄肌",
    "duration_s": 314.863,
    "mode": "concept-explanation",
    "topics": ["Fitness"],
    "keywords": ["薄肌", "代谢适应", "高强度间歇", "持续时间", "训练设计原则", "肌肥大对照"],
    "tldr_oneliner": "薄肌不是吃出来的而是练出来的：高强度短时间 + 代谢适应训练才是正解",
    "chapters": [
        {"title": "一、先定义：什么是「薄肌」", "start": 0, "excerpt": "薄肌的视觉与解剖学定义"},
        {"title": "二、底层视角：把碳水和脂肪一视同仁", "start": 0, "excerpt": "代谢底物切换的概念"},
        {"title": "三、核心矛盾：高强度 vs 持续时间", "start": 0, "excerpt": "强度与时间的取舍空间"},
        {"title": "四、现实例子：代谢适应是可训练的", "start": 0, "excerpt": "代谢路径可塑性举例"},
        {"title": "五、为什么这种训练完美匹配薄肌需求", "start": 0, "excerpt": "训练形式与目标体型的匹配逻辑"},
        {"title": "六、训练设计的三条原则", "start": 0, "excerpt": "强度 / 时长 / 频率三原则"},
        {"title": "七、反推：传统肌肥大训练为什么练不出薄肌", "start": 0, "excerpt": "肌肥大训练为何与薄肌目标相悖"}
    ]
}

# Write each payload as its own JSON file
for slug, payload in PAYLOADS.items():
    out_path = OUT / f"{slug}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

print(f"Wrote {len(PAYLOADS)} payloads to {OUT}")
print(f"Slugs: {sorted(PAYLOADS.keys())}")
