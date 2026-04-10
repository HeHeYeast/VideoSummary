"""CLIP embedding: 每帧算 embedding, 支持语义搜帧.

依赖 open_clip (pip install open_clip_torch).
如果装不上则 graceful fallback, search_frames 退化为关键词匹配.

设计参考: AGENT_DESIGN.md §3.4
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# 尝试导入 open_clip, 失败则标记不可用
_HAS_CLIP = False
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None

try:
    import open_clip
    import torch
    from PIL import Image as PILImage
    _HAS_CLIP = True
except ImportError:
    log.info("open_clip 未安装, CLIP embedding 不可用. "
             "安装: pip install open_clip_torch")


def _ensure_model():
    """懒加载 CLIP 模型."""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is not None:
        return True
    if not _HAS_CLIP:
        return False

    try:
        model_name = "ViT-B-32"
        pretrained = "laion2b_s34b_b79k"
        log.info("加载 CLIP 模型: %s/%s", model_name, pretrained)
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        _clip_tokenizer = open_clip.get_tokenizer(model_name)
        _clip_model.eval()
        return True
    except Exception as e:
        log.warning("CLIP 模型加载失败: %s", e)
        return False


def compute_embeddings(
    frame_paths: list[str],
    output_path: str | Path,
    batch_size: int = 16,
) -> np.ndarray | None:
    """计算所有帧的 CLIP embedding, 保存到 .npy 文件.

    Returns:
        embeddings array (n_frames, dim) 或 None (如果 CLIP 不可用)
    """
    if not _ensure_model():
        log.warning("CLIP 不可用, 跳过 embedding 计算")
        return None

    import torch
    from PIL import Image as PILImage

    all_embs = []
    for i in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[i:i + batch_size]
        images = []
        for p in batch_paths:
            try:
                img = PILImage.open(p).convert("RGB")
                images.append(_clip_preprocess(img))
            except Exception as e:
                log.warning("CLIP 处理图片失败 %s: %s", p, e)
                # 用零向量占位
                images.append(torch.zeros(3, 224, 224))

        batch = torch.stack(images)
        with torch.no_grad():
            embs = _clip_model.encode_image(batch)
            embs = embs / embs.norm(dim=-1, keepdim=True)  # L2 归一化
            all_embs.append(embs.cpu().numpy())

    if not all_embs:
        return None

    embeddings = np.concatenate(all_embs, axis=0)
    output_path = Path(output_path)
    np.save(output_path, embeddings)
    log.info("CLIP embeddings 保存: %s (%s)", output_path, embeddings.shape)
    return embeddings


def search_frames(
    query: str,
    embeddings_path: str | Path,
    frame_ids: list[str],
    top_k: int = 10,
) -> list[dict]:
    """用文本 query 搜索最相关的帧 (余弦相似度).

    AGENT_DESIGN.md §4.1: search_frames 图文检索.

    Returns:
        list of {frame_id, score} 按相关性降序, 最多 top_k 个.
        如果 CLIP 不可用, 返回空列表.
    """
    if not _ensure_model():
        return []

    import torch

    emb_path = Path(embeddings_path)
    if not emb_path.exists():
        log.warning("embeddings 文件不存在: %s", emb_path)
        return []

    embeddings = np.load(emb_path)
    if len(embeddings) != len(frame_ids):
        log.warning("embeddings 数量 (%d) 和 frame_ids (%d) 不匹配",
                    len(embeddings), len(frame_ids))
        return []

    # 编码查询文本
    tokens = _clip_tokenizer([query])
    with torch.no_grad():
        text_emb = _clip_model.encode_text(tokens)
        text_emb = text_emb / text_emb.norm(dim=-1, keepdim=True)
        text_emb = text_emb.cpu().numpy()

    # 余弦相似度
    scores = (embeddings @ text_emb.T).flatten()
    top_indices = scores.argsort()[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "frame_id": frame_ids[idx],
            "score": float(scores[idx]),
        })
    return results
