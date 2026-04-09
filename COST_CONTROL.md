# VideoSummary 成本控制与 API 资源设计

## 一、VectorEngine 平台关键信息（已实测）

### Base URL & 认证
- **Base URL**：`https://api.vectorengine.ai/v1`
- **协议**：OpenAI 兼容
- **认证**：Header `Authorization: Bearer <key>`
- **余额查询**：Web 页面 `https://chaxun.wlai.vip/`（无公开 API，需手动登录查）
- **令牌**：用户提供
  - `KEY_CHEAP` = `sk-yMRLn9qEMl7DQZYWx7Rlp1hJ3ztkpv98Yy0Uj8RW6Fdq75YD`
  - `KEY_QUALITY` = `sk-yMRLn9qEMl7DQZYWx7Rlp1hJ3ztkpv98Yy0Uj8RW6Fdq75YD`
  - （目前是同一个 key，后续可分组管理）

### 实测可用模型清单（从 `/v1/models` 拉取，共 200+ 模型）

**关键发现：默认分组下 Claude 系列不出现**（要么需切到"官转 Claude"6x~16x 分组，要么这个 key 没开 Claude 权限）。**所以方案必须避开 Claude，主用 DeepSeek / Gemini / Qwen / GLM。** 这是个好消息——这些模型本来就便宜。

#### 文本/总结候选

| 模型 ID | 类型 | 适用环节 |
|---|---|---|
| `deepseek-v3.2` ⭐ | 中文强、便宜 | 章节总结、锚点扫描、视频类型识别 |
| `deepseek-v3.1` | 同上 | 备选 |
| `glm-4.6` ⭐ | 中文新模型 | Critique（换模型挑刺） |
| `glm-4.5-air` | 极便宜小模型 | 视频类型识别一类轻量任务 |
| `gemini-2.5-pro` | 长上下文强 | Final revise 精修（质量关） |
| `gemini-2.5-flash` ⭐ | 极快极便宜 | map 阶段总结 |
| `qwen3-max` / `qwen3-30b-a3b` | 通义千问中文 | 兜底 |
| `kimi-k2` | 长上下文 | 长视频备选 |
| `gpt-5-mini` / `gpt-5-nano` | OpenAI 入门 | 兜底 |

#### 视觉理解候选（**调用最多的环节，必须便宜**）

| 模型 ID | 备注 |
|---|---|
| `qwen3-vl-plus` ⭐ | 通义千问视觉，便宜，中文场景强 |
| `qwen-vl-max` | 通义视觉旗舰 |
| `gemini-2.5-flash` ⭐ | Gemini 视觉支持，速度快 |
| `gemini-3-flash-preview` | 更新版 |
| `gpt-4o-mini` | OpenAI 兜底 |

#### ASR 候选

| 模型 ID | 备注 |
|---|---|
| `whisper-1` | OpenAI Whisper |
| `gpt-4o-transcribe` ⭐ | 比 whisper-1 更强 |
| `gpt-4o-mini-transcribe` | 更便宜 |

**主路径仍是本地 SenseVoice**（免费，0 成本），云 ASR 仅作兜底。

#### 嵌入（M3 RAG）

| 模型 ID | 备注 |
|---|---|
| `text-embedding-3-small` | 便宜首选 |
| `text-embedding-3-large` | 质量备选 |

---

## 二、严格成本上限

### 总预算

- **正式运行**：**¥0.1 ~ ¥0.5 / 视频**
- **测试阶段**：**< ¥0.1 / 次**
- **超过即报错退出**（硬熔断）

### 各环节硬上限（按"正式 ¥0.5 视频"分配）

| 环节 | 预算上限 | 调用次数硬上限 | 兜底动作 |
|---|---|---|---|
| 视频类型识别 | ¥0.005 | 1 次 | 失败默认走"教程"类型 |
| ASR（本地） | ¥0 | — | — |
| 关键帧抽取（本地） | ¥0 | — | 帧数硬上限见下 |
| **视觉描述（最大头）** | **¥0.20** | **≤ 50 次调用** | 超出按时间均匀降采样 |
| OCR 兜底 | ¥0.05 | ≤ 10 次 | 跳过 |
| LLM 锚点扫描 | ¥0.02 | 1 次 | 跳过则只用主流程帧 |
| 章节总结 (map) | ¥0.10 | ≤ 8 段 | 章节合并粒度变粗 |
| 章节合并 (reduce) | ¥0.03 | 1 次 | — |
| Critique | ¥0.03 | 1 次 | M1 跳过 |
| Revise | ¥0.05 | 1 次 | M1 跳过 |
| **合计** | **≤ ¥0.48** | | |

### 测试模式（< ¥0.1）

- **关键帧硬上限：≤ 10 张**（够看出 pipeline 是否正确）
- **章节数：≤ 2 段**
- **跳过 critique-revise**
- **优先选最便宜模型**（gemini-2.5-flash / glm-4.5-air / deepseek-v3.2）
- **强制超时与 token 上限**：每次 LLM 调用 max_tokens ≤ 800

---

## 三、成本控制工程实现

成本控制不是"事后估算"，而是**在每次调用前后强制扣账，超出即中断**。

### 设计：BudgetGuard 中间层

所有 API 调用都必须经过一个 `BudgetGuard` 包装：

```python
class BudgetGuard:
    def __init__(self, total_budget_cny: float):
        self.total = total_budget_cny
        self.spent = 0.0
        self.calls = defaultdict(int)        # 按 stage 计数
        self.stage_limits = {...}             # 每个 stage 的硬上限
        self.call_limits = {...}              # 每个 stage 的次数上限

    def precheck(self, stage: str, est_cost: float):
        if self.calls[stage] >= self.call_limits[stage]:
            raise BudgetExceeded(f"{stage} 已达调用次数上限")
        if self.spent + est_cost > self.total:
            raise BudgetExceeded(f"预算 {self.total} 即将超出")
        if self.spent_per_stage[stage] + est_cost > self.stage_limits[stage]:
            raise BudgetExceeded(f"{stage} 阶段预算超出")

    def commit(self, stage: str, actual_cost: float):
        self.spent += actual_cost
        self.spent_per_stage[stage] += actual_cost
        self.calls[stage] += 1
```

### 每次 LLM 调用的标准流程

```python
def call_llm(stage, model, messages, max_tokens):
    est = estimate_cost(model, messages, max_tokens)   # 用 tiktoken 估算
    budget.precheck(stage, est)
    resp = client.chat.completions.create(...)
    actual = compute_cost(model, resp.usage)            # 用真实 usage 算
    budget.commit(stage, actual)
    log_call(stage, model, actual, resp.usage)
    return resp
```

### 关键帧硬上限的执行点

```python
MAX_FRAMES_PROD = 50
MAX_FRAMES_TEST = 10

def select_frames(candidates, mode):
    cap = MAX_FRAMES_TEST if mode == 'test' else MAX_FRAMES_PROD
    if len(candidates) <= cap:
        return candidates
    # 超过上限：按 score 排序取 top-K，或按时间均匀降采样
    return uniform_subsample(candidates, cap)
```

**这一步决定了视觉调用绝对不会超**——上游帧多少都行，到这里硬砍。

### 价格表硬编码（基于实测推断的保守估算）

由于平台没暴露每模型的精确单价，我们按"官方价 × 倍率（默认 1x，限时特价 0.6x）"做保守估算，**估算值故意偏高 20%** 以留余地：

```python
# 单位：CNY per 1M tokens (input, output)
# 倍率默认按 1x（默认分组），实际可能更低
PRICE_TABLE = {
    "gemini-2.5-flash":     (0.7,  2.8),
    "gemini-2.5-pro":       (8.0,  24.0),
    "deepseek-v3.2":        (1.0,  4.0),
    "deepseek-v3.1":        (1.0,  4.0),
    "glm-4.5-air":          (0.5,  2.0),
    "glm-4.6":              (3.0,  10.0),
    "qwen3-vl-plus":        (3.0,  9.0),
    "qwen-vl-max":          (15.0, 45.0),
    "gpt-4o-mini":          (1.5,  6.0),
    # ASR (per minute)
    "whisper-1":            ("per_min", 0.04),
    "gpt-4o-transcribe":    ("per_min", 0.05),
}
```

**首次跑通后**：把真实 usage 和 vectorengine 后台的实际扣费做对比，校准价格表。M2 阶段把校准后的表存起来。

---

## 四、推荐的环节-模型映射（v3，避开 Claude）

| 环节 | 主选模型 | 备选 | 调用上限 |
|---|---|---|---|
| 视频类型识别 | `glm-4.5-air` | `deepseek-v3.2` | 1 |
| ASR | **本地 SenseVoice** | `gpt-4o-mini-transcribe`（云兜底） | 不限 |
| 视觉描述 | `qwen3-vl-plus` ⭐ | `gemini-2.5-flash` | **≤ 50** |
| OCR 兜底 | `qwen3-vl-plus`（同上即可） | — | ≤ 10 |
| LLM 锚点扫描 | `deepseek-v3.2` | `gemini-2.5-flash` | 1 |
| 章节总结 (map) | `deepseek-v3.2` | `gemini-2.5-flash` | ≤ 8 |
| 章节合并 (reduce) | `deepseek-v3.2` | `gemini-2.5-pro` | 1 |
| Critique | `glm-4.6`（换模型挑刺） | `gemini-2.5-pro` | 1 |
| Revise | `gemini-2.5-pro` | `deepseek-v3.2` | 1 |

**关键设计**：Critique 故意用**和 Draft 不同家族**的模型（DeepSeek 写、GLM 挑刺），避免同模型盲点。

---

## 五、测试预算守护配置示例

```yaml
# config/budget_test.yaml
mode: test
total_budget_cny: 0.10
stage_limits:
  type_detect:    0.005
  vision:         0.04
  ocr:            0.01
  anchor:         0.005
  map_summary:    0.025
  reduce:         0.005
  critique:       0       # 测试阶段跳过
  revise:         0       # 测试阶段跳过
call_limits:
  type_detect:    1
  vision:         10      # 关键帧硬上限
  ocr:            3
  anchor:         1
  map_summary:    2       # 测试只切 2 段
  reduce:         1
max_tokens_per_call: 800
fail_fast: true            # 超预算立即抛错退出
```

```yaml
# config/budget_prod.yaml
mode: prod
total_budget_cny: 0.50
stage_limits:
  type_detect:    0.005
  vision:         0.20
  ocr:            0.05
  anchor:         0.02
  map_summary:    0.10
  reduce:         0.03
  critique:       0.03
  revise:         0.05
call_limits:
  type_detect:    1
  vision:         50
  ocr:            10
  anchor:         1
  map_summary:    8
  reduce:         1
  critique:       1
  revise:         1
max_tokens_per_call: 2000
fail_fast: true
```

---

## 六、待办

- [x] 拿到 base_url、key、模型清单
- [x] 设计预算守护与硬上限
- [ ] 你确认：Critique/Revise 在测试阶段是否完全跳过（我建议跳过）
- [ ] 你确认：测试视频是 BV1C9QCBdE1U（Godot 教程）
- [ ] ffmpeg 安装完成后告诉我
- [ ] 我开始写 M1 项目骨架（含 BudgetGuard、价格表、3 个 client：chat / vision / asr 本地）
- [ ] 首次跑通后用真实 usage 校准价格表

---

## 七、风险提示

1. **价格表是估算的**：首次跑完务必去 `chaxun.wlai.vip` 网页查实际扣费，校准 PRICE_TABLE。**第一次跑测试视频时盯紧网页余额变化**。
2. **同一个 key 可能没开 Claude 权限**：实测 `/v1/models` 返回 200+ 模型但无 `claude-*`。这反而**强制我们走更便宜的路线**，对预算友好。
3. **限时特价 0.6x 分组需要后台单独建令牌**：如果你只有一个 key，目前是默认 1x。要拿到 0.6x，需要去 vectorengine 后台**新建一个限时特价分组的令牌**。建后告诉我，我把 KEY_CHEAP 替换。
4. **8GB 显存**：本地 SenseVoice 够用；若 ASR 不准要切 WhisperX large-v3 也能跑，但 Python 3.13 可能装不上 funasr/whisperx，**建议你装 Python 3.11 venv 备用**。
