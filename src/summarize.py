"""v4 文档生成: outline → 逐 section 写作 → polish → 装配.

设计来源:
- Stanford STORM: 不同 stage 用不同模型 (大纲用便宜的, 写手用强的)
- LongWriter / AgentWrite (清华 ICLR 2025): 写手 prompt 模板,
  每段独立调用, 输入 = 完整指令 + 完整大纲 + 已写好的所有正文 + 当前 step
- GPT-Researcher detailed mode: polish 阶段反重复

参考: https://github.com/THUDM/LongWriter/tree/main/agentwrite
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .asr import Segment, format_transcript
from .vision import FrameDescription
from .llm_client import LLMClient
from .budget import BudgetExceeded

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Stage 1: Outline
# ────────────────────────────────────────────────────────────

OUTLINE_PROMPT = """你是教学文档的结构规划师. 给定一段教学视频的字幕和关键帧描述,
请规划出一份详细教程文档的大纲. 大纲必须以 JSON 输出, 可被 json.loads 直接解析.

# 视频信息
标题: {title}
时长: {duration}

# 字幕 (带时间戳, 覆盖完整视频)
{transcript}

# 关键帧 (仅供参考, 帧归属由代码自动按时间戳分配, 你不需要输出 frame_ids)
{frames}

# 输出要求 (严格 JSON)
```json
{{
  "topic": "一句话说明这个教程做什么",
  "sections": [
    {{
      "id": "s1",
      "title": "节标题, 用动词短语 (例: 创建自定义节点)",
      "time_range": [起始秒, 结束秒]
    }}
  ]
}}
```

# 严格要求
1. **时间范围必须覆盖整个视频**, 从 0 到视频总时长. 不要把所有 sections 都挤在开头.
   检查: 最后一节的 time_range[1] 必须接近视频总时长.
2. 按视频时间顺序切分, 每个 section 时间不重叠, 首尾相接.
3. 切分粒度: 按"自然教学步骤"切分, 不要按固定时长. 一个完整步骤一节.
   通常 4-8 节. 不要超过 {max_sections} 节.
4. 每个 section 的标题必须是动词短语, 描述这一步做什么.
5. 只输出 JSON, 不要额外解释, 不要输出 must_cover 或 frame_ids 字段.

现在输出 JSON:"""


def generate_outline(segs: list[Segment], frame_descs: list[FrameDescription],
                     meta: dict, client: LLMClient, model: str,
                     work_dir: Any = None) -> dict:
    transcript = format_transcript(segs)
    frames_text = "\n".join(
        f"[{i}] [{_fmt(f.timestamp)}] {f.description}"
        for i, f in enumerate(frame_descs)
    ) or "(无关键帧)"

    # 长视频字幕压缩: 超过 20k 字符时均匀抽样, 保证覆盖完整时间线而不是只看开头
    transcript_for_outline = _compress_transcript_for_outline(transcript, max_chars=20000)

    prompt = OUTLINE_PROMPT.format(
        title=meta.get("title", ""),
        duration=_fmt(meta.get("duration", 0)),
        transcript=transcript_for_outline,
        frames=frames_text[:3000],
        max_sections=8,
    )

    last_raw = ""
    for attempt in range(2):
        raw = client.chat(
            stage="outline",
            model=model,
            group="cheap",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        last_raw = raw
        if work_dir is not None:
            from pathlib import Path
            Path(work_dir).joinpath(f"outline_raw_{attempt}.txt").write_text(
                raw, encoding="utf-8"
            )
        try:
            return _parse_json_strict(raw)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("outline JSON 解析失败 attempt %d: %s", attempt, e)
            if attempt == 0:
                prompt = (
                    "上次输出的 JSON 有语法错误, 请严格按 JSON 规范重新输出 (无注释/无尾逗号):\n\n"
                    + prompt
                )
    raise json.JSONDecodeError(f"两次尝试都失败, 最后输出: {last_raw[:300]}", last_raw, 0)


def _compress_transcript_for_outline(transcript: str, max_chars: int = 20000) -> str:
    """长视频字幕压缩. 均匀抽样保证覆盖完整时间线, 避免 outline 只看开头.

    当字幕超过 max_chars 时, 按行数均匀采样到目标长度.
    保留首尾各 10% 的完整行, 中间部分做 stride 采样.
    """
    if len(transcript) <= max_chars:
        return transcript
    lines = transcript.splitlines()
    if not lines:
        return transcript[:max_chars]
    # 估算每行平均字符数 → 目标行数
    avg = max(len(transcript) / len(lines), 1)
    target_lines = int(max_chars / avg)
    if target_lines >= len(lines):
        return transcript[:max_chars]
    head = int(target_lines * 0.15)
    tail = int(target_lines * 0.15)
    middle_target = target_lines - head - tail
    middle_pool = lines[head:len(lines) - tail] if tail > 0 else lines[head:]
    if middle_target > 0 and len(middle_pool) > middle_target:
        stride = len(middle_pool) / middle_target
        middle = [middle_pool[int(i * stride)] for i in range(middle_target)]
    else:
        middle = middle_pool
    result = lines[:head] + ["[... 字幕已按时间均匀抽样 ...]"] + middle + (lines[-tail:] if tail > 0 else [])
    return "\n".join(result)


def assign_frames_to_sections(sections: list[dict],
                               frame_descs: list[FrameDescription]) -> None:
    """按时间戳确定性地把帧分配到 section (in-place 写 frame_ids).

    帧归属是几何问题, LLM 分配容易错分漏分, 代码里做.
    """
    for sec in sections:
        tr = sec.get("time_range", [0, 0])
        start, end = tr[0], tr[1]
        sec["frame_ids"] = [
            i for i, f in enumerate(frame_descs)
            if start <= f.timestamp < end
        ]


def merge_transcript_with_frames(segs: list[Segment],
                                  frame_descs: list[FrameDescription]) -> str:
    """把帧描述按时间戳插入字幕, 形成统一的多模态时间线.

    writer 拿到的不再是两份割裂输入, 而是一条连续叙事:
      [00:00:18] 我们来写 spawn_label 函数
      [00:00:19] 📺 <帧描述: func spawn_label(...)>
      [00:00:20] 注意这里 critical_hit 默认是 false
    """
    events: list[tuple[float, str]] = []
    for s in segs:
        events.append((s.start, f"[{_fmt(s.start)}] {s.text}"))
    for f in frame_descs:
        events.append((f.timestamp, f"[{_fmt(f.timestamp)}] 📺 {f.description}"))
    events.sort(key=lambda x: x[0])
    return "\n".join(line for _, line in events)


def validate_timestamps(md: str, segs: list[Segment], tolerance_sec: float = 5.0) -> tuple[str, list[str]]:
    """扫描 writer 输出中的 [HH:MM:SS], 对不上真实字幕的就替换成最近的有效时间戳.

    判定"有效"标准: 时间戳落在任意 segment [start-tol, end+tol] 范围内.
    幻觉时间戳替换 (而非删除整行), 避免破坏段落结构.

    返回: (清洗后的 md, 被替换的时间戳列表)
    """
    if not segs:
        return md, []

    # 构造每个 segment 的覆盖区间
    intervals = sorted([(s.start, max(s.end, s.start)) for s in segs], key=lambda x: x[0])

    def _is_valid(t: float) -> bool:
        for st, en in intervals:
            if st - tolerance_sec <= t <= en + tolerance_sec:
                return True
        return False

    def _nearest_start(t: float) -> float:
        # 取距离最近的 segment.start
        return min((s for s, _ in intervals), key=lambda x: abs(x - t))

    pattern = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")
    replaced: list[str] = []

    def _sub(m: re.Match) -> str:
        h, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3))
        t = h * 3600 + mm * 60 + ss
        if _is_valid(t):
            return m.group(0)
        # 幻觉: 替换为最近的真实 segment 起点
        nearest = _nearest_start(t)
        replaced.append(f"{m.group(0)}→[{_fmt(nearest)}]")
        return f"[{_fmt(nearest)}]"

    cleaned = pattern.sub(_sub, md)
    return cleaned, replaced


def _parse_json_strict(raw: str) -> dict:
    """从模型输出中提取 JSON. 容错处理 markdown 包裹 + 常见语法错误."""
    raw = raw.strip()
    # 去掉 ```json ``` 包裹
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    # 尝试找第一个 { 到最后一个 }
    if not raw.startswith("{"):
        s = raw.find("{")
        e = raw.rfind("}")
        if s >= 0 and e > s:
            raw = raw[s:e + 1]
    # 直接尝试
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 常见修复: 去尾逗号
    fixed = re.sub(r",(\s*[}\]])", r"\1", raw)
    # 修复: 数字前后多余的逗号
    fixed = re.sub(r"//[^\n]*", "", fixed)  # 去 // 注释
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # 最后尝试: 用 ast.literal_eval (能容忍单引号)
    try:
        import ast
        return ast.literal_eval(fixed)
    except Exception:
        pass
    raise json.JSONDecodeError("无法修复 JSON", raw, 0)


# ────────────────────────────────────────────────────────────
# Stage 2: Section writer (AgentWrite-style)
# ────────────────────────────────────────────────────────────

# 直接借鉴 LongWriter AgentWrite 的 prompt 结构
# https://github.com/THUDM/LongWriter/blob/main/agentwrite/prompts/write.txt
WRITER_PROMPT = """你是教学文档作者. 把一段教学视频的这一小节, 还原为读者照着就能复现的图文教程.
不是会议纪要, 不是大纲, 而是真正的教程: 读者读完应该知道做什么、怎么做、为什么这么做.

# 完整大纲 (知道自己在哪一节, 上下文)
{plan}

# 已写好的前文结尾 (用于衔接, 不要重复)
{written}

# 当前小节
节 ID: {section_id}
节标题: {section_title}
时间范围: {time_range}

# 本节多模态时间线 (字幕 + 关键帧按时间戳合并, 📺 标记画面)
{timeline}

# 写作要求

## 结构 (重要)
- 用 `## {section_title}` 二级标题开头
- 内容按"操作步骤"组织. 每个关键步骤格式如下:
  ```
  [HH:MM:SS] **步骤标题**

  这一步要做什么的简短说明 (1-2 句).

  ![](frames/xxx.jpg)   ← 如果时间线里有这个时间戳附近的 📺 帧, 紧跟在这里

  *为什么这么做*: 一句话解释原因 (如果原视频解释了)
  ```
- 步骤之间空行分隔, 不要把所有步骤糅成一段

## 时间戳 (重要)
- **每个关键步骤开头必须带 [HH:MM:SS]**, 用上面时间线里实际出现的时间戳
- 不要编造时间戳. 不知道用什么时间戳就用最近的字幕时间戳
- 时间戳要紧跟操作语义, 不是均匀洒落

## 图片 (重要)
- 时间线里出现 📺 行就**必须插图**, 用 `![](frames/xxx.jpg)` 语法
  (具体路径看每行 📺 后面的 "插图语法: ![](...)")
- 图片**紧跟在它对应的操作步骤里**, 不要全部堆在小节末尾
- 没有 📺 的步骤不要硬插图, 不要引用其他时间段的图

## 内容
- 用第二人称指令式: "新建一个节点", 不是"作者新建了节点"
- 字幕里出现的代码、函数名、参数名、菜单项, 要原样引用 (用 ` 反引号 ` 或代码块)
- 字幕里没说的细节不要编造. 拿不准就用自然语言描述, 不要瞎猜代码
- 解释"为什么", 不只是"怎么做". 如果原视频说了原因 (例如"这样我们能拿到 Node2D 的位置属性"), 一定要保留
- 不写"综上所述/接下来我们将", 不写开放式结尾

## 代码块
- 行内代码用反引号. 多行代码用 ```语言名 ``` 块
- **本节末尾, 如果且仅如果**本节出现了至少 3 行实际代码, 追加:
  ```
  ### 本节完整代码

  ```语言名
  <把本节散落的代码片段合并成一个可运行的完整段落>
  ```
  ```
- 如果本节根本没代码, 或者代码不到 3 行, **绝对不要**输出 "### 本节完整代码" 这个小节,
  也不要输出 "// 此节未涉及" 这种占位符

## 长度
- 上限 {max_words} 字. 没有下限
- 但教程通常需要 200-500 字才能讲清楚一个步骤. 不要只写一两句话就交差
- 也不要为了凑字数加废话. 信息密度第一

现在输出本节内容:"""


# fallback 链精简: 主模型 + gpt-4o-mini 兜底. kimi/deepseek 长期 429 不放在主链里
WRITER_FALLBACKS = ["gpt-4o-mini"]


def _too_short(text: str, min_chars: int = 80) -> bool:
    return len((text or "").strip()) < min_chars


def write_section(section: dict, plan: dict, written: str,
                  segs: list[Segment], frame_descs: list[FrameDescription],
                  client: LLMClient, model: str) -> str:
    start, end = section.get("time_range", [0, 0])
    # 取该 section 时间窗内的字幕 + 帧, 合并成统一时间线
    win_segs = [s for s in segs if start <= s.start < end]
    frame_ids = section.get("frame_ids", [])
    win_frames = [frame_descs[i] for i in frame_ids if 0 <= i < len(frame_descs)]

    # 把帧带上相对路径, writer 用它生成 ![](path). 相对 summary.md 同目录
    # frame.path 形如 "output\BV1xxx\frames\frame_000001.jpg", 只取最后两段 "frames/frame_000001.jpg"
    def _rel_path(p: str) -> str:
        parts = p.replace("\\", "/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else p

    events: list[tuple[float, str]] = []
    for s in win_segs:
        events.append((s.start, f"[{_fmt(s.start)}] {s.text}"))
    for f in win_frames:
        rp = _rel_path(f.path)
        events.append((f.timestamp,
                       f"[{_fmt(f.timestamp)}] 📺 {f.description}  (插图语法: ![]({rp}))"))
    events.sort(key=lambda x: x[0])
    timeline = "\n".join(line for _, line in events)[:8000]
    if not win_frames:
        timeline += "\n\n⚠️ 本节时间段内没有关键帧, 不要插入任何 ![](...) 图片引用."
    if not timeline.strip():
        timeline = "(无内容)"

    max_words = min(int(section.get("length_budget_words", 600)), 1000)

    # 精简 plan: 只给标题列表, 避免重复 token
    plan_compact = "\n".join(
        f"{i+1}. [{s.get('id')}] {s.get('title')}"
        for i, s in enumerate(plan.get("sections", []))
    )

    # 已写正文如果太长, 截断保留尾部
    written_compact = written[-2000:] if len(written) > 2000 else written

    prompt = WRITER_PROMPT.format(
        plan=plan_compact,
        written=written_compact or "(尚未开始)",
        section_id=section.get("id", ""),
        section_title=section.get("title", ""),
        time_range=f"{_fmt(start)}-{_fmt(end)}",
        timeline=timeline,
        max_words=max_words,
    )
    # 模型 fallback
    candidates = [model] + [m for m in WRITER_FALLBACKS if m != model]
    last_err = None
    for m in candidates:
        try:
            result = client.chat(
                stage="section",
                model=m,
                group="cheap",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(max_words * 2),
            )
            # 只拒绝空输出. 不强求时间戳 (writer 可能故意不带, 后续 validate 只清洗幻觉)
            if not result or len(result.strip()) < 30:
                log.warning("写手 %s 返回空/过短, 尝试下一个", m)
                last_err = RuntimeError(f"{m} returned empty content")
                time.sleep(2)
                continue
            # 时间戳后验校验: 删掉幻觉时间戳
            cleaned, replaced = validate_timestamps(result, segs, tolerance_sec=5.0)
            if replaced:
                log.warning("写手 %s 替换 %d 个幻觉时间戳: %s",
                            m, len(replaced), replaced[:3])
            # 图片白名单: 只允许引用本 section 真正分到的帧, 删掉幻觉路径
            allowed_basenames = {Path(f.path).name for f in win_frames}
            cleaned, dropped_imgs = _strip_unauthorized_images(cleaned, allowed_basenames)
            if dropped_imgs:
                log.warning("写手 %s 引用了未分配的帧, 已删除: %s",
                            m, dropped_imgs[:3])
            # 删除"本节完整代码"小节里只有占位符的情况
            cleaned = _strip_empty_full_code(cleaned)
            return cleaned
        except BudgetExceeded:
            raise
        except Exception as e:
            log.warning("写手 %s 失败 (%s), 尝试下一个", m, type(e).__name__)
            last_err = e
            time.sleep(3)
    raise RuntimeError(f"所有写手模型都失败: {last_err}")


# ────────────────────────────────────────────────────────────
# Stage 3: Polish (轻量, 给衔接 / 去重建议)
# ────────────────────────────────────────────────────────────

POLISH_PROMPT = """下面是一份分节写好的教学文档的"骨架": 每个 section 的标题 + 首句.
请你检查:
1. 章节衔接是否突兀 (上一节结尾和下一节开头是否对应)
2. 是否有明显的重复内容 (多节讲了同一件事)
3. 是否有遗漏的明显步骤 (相邻节之间出现跳跃)

只输出 JSON 格式的修改建议, 形如:
```json
{{
  "issues": [
    {{"section_id": "s2", "type": "transition", "note": "和 s1 衔接突兀, 建议..."}}
  ]
}}
```
如无问题输出 `{{"issues": []}}`.

骨架:
{skeleton}

输出 JSON:"""


def polish_pass(sections_md: list[tuple[str, str]], client: LLMClient,
                model: str) -> dict:
    skeleton_lines = []
    for sid, md in sections_md:
        first_line = next((l for l in md.splitlines() if l.strip()), "")
        first_para = ""
        for l in md.splitlines():
            if l.strip() and not l.startswith("#"):
                first_para = l[:120]
                break
        skeleton_lines.append(f"[{sid}] {first_line}\n  首句: {first_para}")
    skeleton = "\n".join(skeleton_lines)

    try:
        raw = client.chat(
            stage="polish",
            model=model,
            group="cheap",
            messages=[{"role": "user", "content": POLISH_PROMPT.format(skeleton=skeleton)}],
            max_tokens=600,
        )
        return _parse_json_strict(raw)
    except Exception as e:
        log.warning("polish 失败, 跳过: %s", e)
        return {"issues": []}


# ────────────────────────────────────────────────────────────
# Stage 4: 装配 (本地, 0 调用)
# ────────────────────────────────────────────────────────────

_PLACEHOLDER_PATTERNS = [
    "未涉及", "此处添加", "暂无代码", "no code", "// TODO",
    "# TODO", "省略", "...",
]


def _is_placeholder(code: str) -> bool:
    """识别 LLM 输出的代码占位符 (没真代码却写了个壳)."""
    s = code.strip()
    if len(s) < 10:
        return True
    # 全是注释行 / 占位符短语
    non_comment = [l for l in s.splitlines() if l.strip() and not l.strip().startswith(("#", "//"))]
    if not non_comment:
        return True
    if any(p in s for p in _PLACEHOLDER_PATTERNS):
        return True
    return False


def extract_code_blocks(md: str) -> list[tuple[str, str]]:
    """从 markdown 提取所有代码块, 返回 [(语言, 代码)]. 自动过滤占位符."""
    pattern = re.compile(r"```(\w*)\n(.*?)\n```", re.DOTALL)
    blocks = [(m.group(1) or "", m.group(2)) for m in pattern.finditer(md)]
    return [(lang, code) for lang, code in blocks if not _is_placeholder(code)]


def _strip_unauthorized_images(md: str, allowed_basenames: set[str]) -> tuple[str, list[str]]:
    """删除 ![](frames/xxx.jpg) 中 basename 不在白名单的图片引用 (整行删).

    防止 writer 在没有帧的 section 凭记忆塞别处的图片.
    """
    pattern = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
    dropped: list[str] = []
    out_lines: list[str] = []
    for line in md.splitlines():
        m = pattern.search(line)
        if m:
            base = Path(m.group(1)).name
            if base not in allowed_basenames:
                dropped.append(base)
                continue  # 删除整行图片引用
        out_lines.append(line)
    return "\n".join(out_lines), dropped


def _strip_empty_full_code(md: str) -> str:
    """如果 '### 本节完整代码' 后面只有占位符代码块, 整个小节删掉."""
    pattern = re.compile(
        r"###\s*本节完整代码\s*\n(.*?)(?=\n##|\Z)",
        re.DOTALL,
    )
    def _check(m: re.Match) -> str:
        body = m.group(1)
        blocks = re.findall(r"```(\w*)\n(.*?)\n```", body, re.DOTALL)
        if not blocks:
            return ""
        # 任何一个非占位符代码块都保留整个小节
        if any(not _is_placeholder(code) for _, code in blocks):
            return m.group(0)
        return ""
    return pattern.sub(_check, md).rstrip() + "\n"


def _extract_full_code_blocks(md: str) -> list[tuple[str, str]]:
    """只提取 '### 本节完整代码' 小节后面的代码块. 找不到则返回空."""
    m = re.search(r"###\s*本节完整代码\s*\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if not m:
        return []
    return extract_code_blocks(m.group(1))


def assemble(sections_md: list[tuple[str, str]], outline: dict, meta: dict,
             polish_issues: dict, planned_sections: int = 0,
             missing_sections: list[dict] | None = None) -> str:
    title = meta.get("title", "")
    out = [f"# {title}\n"]
    out.append(
        f"> UP主: {meta.get('uploader','')} | "
        f"时长: {_fmt(meta.get('duration', 0))} | "
        f"原视频: {meta.get('url','')}\n"
    )

    # ⚠️ 不完整警示 banner (顶部显著位置)
    if missing_sections:
        out.append("> ⚠️ **文档不完整**: 本文档在生成过程中因预算或调用限制提前终止.\n"
                   f"> 已完成 {len(sections_md)}/{planned_sections} 节, "
                   f"以下章节**未被写入**:\n> ")
        for s in missing_sections:
            tr = s.get("time_range", [0, 0])
            out.append(f"> - **{s.get('id','?')}** {s.get('title','?')} "
                       f"({_fmt(tr[0])}-{_fmt(tr[1])})")
        out.append("> \n> 请扩大预算或提高 call_limits.section 后重跑.\n")

    if outline.get("topic"):
        out.append(f"## 这个教程做什么\n{outline['topic']}\n")

    # TOC (只列已生成的节)
    written_ids = {sid for sid, _ in sections_md}
    out.append("## 目录")
    for i, s in enumerate(outline.get("sections", []), 1):
        sid = s.get("id", "")
        mark = "" if sid in written_ids else " ⚠️ 未生成"
        out.append(f"{i}. [{s.get('title','')}](#{sid}){mark}")
    out.append("")

    # 正文
    out.append("## 步骤详解\n")
    for sid, md in sections_md:
        out.append(f'<a id="{sid}"></a>')
        out.append(md.strip())
        out.append("")

    # 完整代码合集: 优先用 writer 输出的 "### 本节完整代码" 小节
    all_code: list[tuple[str, str]] = []
    seen = set()
    for sid, md in sections_md:
        full_blocks = _extract_full_code_blocks(md)
        blocks = full_blocks if full_blocks else extract_code_blocks(md)
        for lang, code in blocks:
            key = code.strip()
            if key and key not in seen and len(key) > 10:  # 过滤 1-2 行的碎片
                seen.add(key)
                all_code.append((lang, code))
    if all_code:
        out.append("## 完整代码合集\n")
        for lang, code in all_code:
            out.append(f"```{lang}\n{code}\n```\n")

    # polish 建议
    if polish_issues.get("issues"):
        out.append("## 编辑备注 (polish 阶段建议, 待人工核对)\n")
        for issue in polish_issues["issues"]:
            out.append(
                f"- [{issue.get('section_id','')}] **{issue.get('type','')}**: "
                f"{issue.get('note','')}"
            )

    return "\n".join(out)


# ────────────────────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────────────────────

def generate_document(segs: list[Segment], frame_descs: list[FrameDescription],
                      meta: dict, client: LLMClient,
                      outline_model: str, writer_model: str,
                      polish_model: str, work_dir: Any = None) -> str:
    # Stage 1: outline (带缓存)
    log.info("[v4] 生成大纲...")
    outline = None
    if work_dir is not None:
        from pathlib import Path
        outline_cache = Path(work_dir) / "outline.json"
        if outline_cache.exists():
            try:
                outline = json.loads(outline_cache.read_text(encoding="utf-8"))
                log.info("[v4] 大纲缓存命中")
            except Exception:
                outline = None
    if outline is None:
        try:
            outline = generate_outline(segs, frame_descs, meta, client,
                                       outline_model, work_dir=work_dir)
            if work_dir is not None:
                from pathlib import Path
                Path(work_dir).joinpath("outline.json").write_text(
                    json.dumps(outline, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except BudgetExceeded as e:
            log.error("outline 阶段预算耗尽: %s", e)
            return f"# {meta.get('title','')}\n\n[outline 失败: {e}]\n\n{format_transcript(segs)}"
        except (json.JSONDecodeError, ValueError) as e:
            log.error("outline JSON 解析失败: %s", e)
            return f"# {meta.get('title','')}\n\n[outline JSON 解析失败]\n\n{format_transcript(segs)}"

    sections = outline.get("sections", [])
    # 代码确定性分配帧 ID (不再依赖 LLM)
    assign_frames_to_sections(sections, frame_descs)
    log.info("[v4] 大纲含 %d sections, 帧已按时间戳分配", len(sections))

    # Stage 2: 逐节写作
    sections_md: list[tuple[str, str]] = []
    written_acc = ""
    stopped_early = False
    for i, sec in enumerate(sections):
        log.info("[v4] 写第 %d/%d 节: %s", i + 1, len(sections), sec.get("title", ""))
        if i > 0:
            time.sleep(5)  # 缓解中转站 429
        try:
            md = write_section(sec, outline, written_acc, segs, frame_descs,
                               client, writer_model)
            sections_md.append((sec.get("id", f"s{i+1}"), md.strip()))
            written_acc += "\n\n" + md.strip()
        except BudgetExceeded as e:
            log.warning("section 阶段预算耗尽, 停止于第 %d 节: %s", i + 1, e)
            stopped_early = True
            break
        except Exception as e:
            log.error("section %d 调用失败 (跳过): %s", i + 1, e)
            continue

    if not sections_md:
        return f"# {meta.get('title','')}\n\n[所有 section 都失败了]"

    # 计算未写入的章节 (预算耗尽 or 调用失败)
    written_ids = {sid for sid, _ in sections_md}
    missing = [s for s in sections if s.get("id") not in written_ids]

    # Stage 3: polish
    log.info("[v4] polish...")
    polish_issues = polish_pass(sections_md, client, polish_model)

    # Stage 4: 装配
    log.info("[v4] 装配...")
    return assemble(sections_md, outline, meta, polish_issues,
                    planned_sections=len(sections),
                    missing_sections=missing)


# ────────────────────────────────────────────────────────────
# 工具
# ────────────────────────────────────────────────────────────

def _fmt(sec: float) -> str:
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
