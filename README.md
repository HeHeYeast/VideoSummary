# VideoSummary

把 B 站视频转成结构化 Markdown 学习笔记. 严格预算控制.

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 VE_KEY_CHEAP / VE_KEY_QUALITY

# 3. 装 ffmpeg (Windows)
# 下载 https://www.gyan.dev/ffmpeg/builds/ release-essentials, bin 加 PATH

# 4. 跑测试模式 (预算 ¥0.10)
python -m src.cli https://www.bilibili.com/video/BV1C9QCBdE1U --mode test

# 5. 跑正式模式 (预算 ¥0.50)
python -m src.cli https://www.bilibili.com/video/BV1C9QCBdE1U --mode prod
```

## 项目结构

```
config/             预算配置 (test/prod)
src/
  budget.py         预算守护 + 价格表 (USD 内部, CNY 显示)
  llm_client.py     VectorEngine 中转客户端
  download.py       yt-dlp 下载
  asr.py            faster-whisper 转录 (含 VAD 反幻觉)
  frames.py         ffmpeg 抽帧 + pHash 去重
  vision.py         视觉模型描帧
  summarize.py      map-reduce 总结
  pipeline.py       端到端编排
  cli.py            入口
```

## 设计文档

- `PROJECT_DESIGN.md` - 整体架构
- `PIPELINE_CANDIDATES.md` - 各环节候选方案
- `COST_CONTROL.md` - 成本控制策略
