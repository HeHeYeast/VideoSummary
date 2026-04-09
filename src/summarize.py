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

# 字幕 (带时间戳)
{transcript}

# 关键帧
{frames}

# 输出要求 (严格 JSON)
```json
{{
  "topic": "一句话说明这个教程做什么",
  "sections": [
    {{
      "id": "s1",
      "title": "节标题, 用动词短语 (例: 创建自定义节点)",
      "time_range": [起始秒, 结束秒],
      "must_cover": [
        "本节必须涵盖的具体要点 1",
        "本节必须涵盖的具体要点 2",
        "..."
      ],
      "frame_ids": [属于本节的关键帧序号列表, 从 0 开始],
      "length_budget_words": 800
    }}
  ]
}}
```

# 严格要求
1. 按视频时间顺序切分 sections, 每个 section 时间不重叠
2. 切分粒度: 按"自然教学步骤"切分, 不要按固定时长. 一个步骤一节
3. 每个 section 的 must_cover 至少 3 条, 必须是从字幕中实际出现的具体内容,
   不要虚构. 涉及代码/参数/操作的尽量列出具体名字
4. **每张关键帧必须分配到唯一一个 section**, 不要漏分或重分
5. length_budget_words 上限 1000 字, 根据本节内容多寡设 300-1000 之间
6. 只输出 JSON, 不要额外解释

现在输出 JSON:"""


def generate_outline(segs: list[Segment], frame_descs: list[FrameDescription],
                     meta: dict, client: LLMClient, model: str,
                     work_dir: Any = None) -> dict:
    transcript = format_transcript(segs)
    frames_text = "\n".join(
        f"[{i}] [{_fmt(f.timestamp)}] {f.description}"
        for i, f in enumerate(frame_descs)
    ) or "(无关键帧)"

    prompt = OUTLINE_PROMPT.format(
        title=meta.get("title", ""),
        duration=_fmt(meta.get("duration", 0)),
        transcript=transcript[:20000],
        frames=frames_text[:3000],
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
WRITER_PROMPT = """你是一个优秀的教学文档写作助手. 我会给你一份原始的写作指令、完整的写作计划、
我已经写好的正文, 以及当前要写的小节. 请你根据这些信息继续写下一节.

# 写作指令
把一段教学视频的字幕和关键帧, 还原为一份详细的图文教程. 读者应该能照着文档完整复现操作,
不需要回看视频. 用第二人称指令式 ("新建一个节点", 不是"作者新建了节点"). 完整保留代码,
口述讲到的代码必须放进 ```代码块 标注语言. 解释每一步的"为什么". 严禁省略.

# 完整写作计划 (大纲)
{plan}

# 已写好的正文
{written}

# 当前要写的小节
节 ID: {section_id}
节标题: {section_title}
本节必须涵盖:
{must_cover}

# 本节对应的字幕原文 (时间 {time_range})
{transcript_window}

# 本节对应的关键帧
{frames_window}

# 严格要求
1. 只输出本节内容, **不要重复已写好的正文**
2. 字数 {min_words}-{max_words} 字, 不要少于下限, 不要超过上限
3. 用 ## 二级标题开头, 标题就是节标题
4. 每个步骤带 [HH:MM:SS] 时间戳
5. 出现的代码必须用 ```语言 ``` 包裹完整, 不要省略
6. 不要写"综上所述/总而言之/接下来我们将"等转场废话
7. 不要写开放式结尾, 这是一份连续文档的中间部分

现在输出本节内容:"""


WRITER_FALLBACKS = ["deepseek-v3.2", "gpt-4o-mini", "kimi-k2", "glm-4.6"]


def _too_short(text: str, min_chars: int = 80) -> bool:
    return len((text or "").strip()) < min_chars


def write_section(section: dict, plan: dict, written: str,
                  segs: list[Segment], frame_descs: list[FrameDescription],
                  client: LLMClient, model: str) -> str:
    start, end = section.get("time_range", [0, 0])
    # 取该 section 时间窗内的字幕
    win_segs = [s for s in segs if start <= s.start < end]
    transcript_window = format_transcript(win_segs)[:6000]

    # 取该 section 分到的关键帧
    frame_ids = section.get("frame_ids", [])
    win_frames = [frame_descs[i] for i in frame_ids if 0 <= i < len(frame_descs)]
    frames_window = "\n".join(
        f"[{_fmt(f.timestamp)}] {f.description}" for f in win_frames
    ) or "(无)"

    must_cover = "\n".join(f"- {x}" for x in section.get("must_cover", []))
    budget_words = section.get("length_budget_words", 600)
    max_words = min(int(budget_words), 1000)
    min_words = max(int(max_words * 0.5), 200)

    # 精简 plan: 只给标题列表, 避免重复 token
    plan_compact = "\n".join(
        f"{i+1}. [{s.get('id')}] {s.get('title')}"
        for i, s in enumerate(plan.get("sections", []))
    )

    # 已写正文如果太长, 截断保留尾部 (AgentWrite 是全量, 但我们要省 token)
    written_compact = written[-3000:] if len(written) > 3000 else written

    prompt = WRITER_PROMPT.format(
        plan=plan_compact,
        written=written_compact or "(尚未开始)",
        section_id=section.get("id", ""),
        section_title=section.get("title", ""),
        must_cover=must_cover,
        time_range=f"{_fmt(start)}-{_fmt(end)}",
        transcript_window=transcript_window,
        frames_window=frames_window,
        min_words=min_words,
        max_words=max_words,
    )
    # 模型 fallback: 主选 model, 失败/返回过短后按 WRITER_FALLBACKS 顺序尝试
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
            if _too_short(result):
                log.warning("写手 %s 返回过短, 尝试下一个", m)
                last_err = RuntimeError(f"{m} returned too short content")
                time.sleep(2)
                continue
            return result
        except BudgetExceeded:
            raise
        except Exception as e:
            log.warning("写手 %s 失败 (%s), 尝试下一个", m, type(e).__name__)
            last_err = e
            time.sleep(3)
    raise RuntimeError(f"所有写手模型都失败/返回过短: {last_err}")


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

def extract_code_blocks(md: str) -> list[tuple[str, str]]:
    """从 markdown 提取所有代码块, 返回 [(语言, 代码)]."""
    pattern = re.compile(r"```(\w*)\n(.*?)\n```", re.DOTALL)
    return [(m.group(1) or "", m.group(2)) for m in pattern.finditer(md)]


def assemble(sections_md: list[tuple[str, str]], outline: dict, meta: dict,
             polish_issues: dict) -> str:
    title = meta.get("title", "")
    out = [f"# {title}\n"]
    out.append(
        f"> UP主: {meta.get('uploader','')} | "
        f"时长: {_fmt(meta.get('duration', 0))} | "
        f"原视频: {meta.get('url','')}\n"
    )
    if outline.get("topic"):
        out.append(f"## 这个教程做什么\n{outline['topic']}\n")

    # TOC
    out.append("## 目录")
    for i, s in enumerate(outline.get("sections", []), 1):
        out.append(f"{i}. [{s.get('title','')}](#{s.get('id','')})")
    out.append("")

    # 正文
    out.append("## 步骤详解\n")
    for sid, md in sections_md:
        # 给 section 加 anchor
        out.append(f'<a id="{sid}"></a>')
        out.append(md.strip())
        out.append("")

    # 完整代码合集
    all_code: list[tuple[str, str]] = []
    seen = set()
    for _, md in sections_md:
        for lang, code in extract_code_blocks(md):
            key = code.strip()
            if key and key not in seen:
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
    log.info("[v4] 大纲含 %d sections", len(sections))

    # Stage 2: 逐节写作
    sections_md: list[tuple[str, str]] = []
    written_acc = ""
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
            break
        except Exception as e:
            log.error("section %d 调用失败 (跳过): %s", i + 1, e)
            continue

    if not sections_md:
        return f"# {meta.get('title','')}\n\n[所有 section 都失败了]"

    # Stage 3: polish
    log.info("[v4] polish...")
    polish_issues = polish_pass(sections_md, client, polish_model)

    # Stage 4: 装配
    log.info("[v4] 装配...")
    return assemble(sections_md, outline, meta, polish_issues)


# ────────────────────────────────────────────────────────────
# 工具
# ────────────────────────────────────────────────────────────

def _fmt(sec: float) -> str:
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
