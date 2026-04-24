"""JSON 持久化存储 - 统一的读写管理"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger


class Store:
    """JSON 存储管理器，提供原子写入功能。"""

    @staticmethod
    def load_json(path: Path, default_value: Any) -> Any:
        """读取 JSON 文件，失败时返回默认值。"""
        if not path.exists():
            return default_value
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败 {}: {}", path, e)
            return default_value
        except Exception as e:
            logger.error("读取文件失败 {}: {}", path, e)
            return default_value

    @staticmethod
    def save_json(path: Path, data: Any) -> None:
        """原子写入 JSON 文件。

        使用 tempfile + os.replace 实现原子写入，避免写入中断导致文件损坏。
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp", prefix="store_", dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(path))
                logger.debug("已保存数据文件 {} ({}条记录)", path,
                           len(data) if isinstance(data, (list, dict)) else 0)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error("保存文件失败 {}: {}", path, e)

    @staticmethod
    def deep_copy_dict(d: dict) -> dict:
        """深拷贝字典，用于默认值。"""
        import copy
        return copy.deepcopy(d)
