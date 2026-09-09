"""匿名化モジュール。

付帯情報（タグ）に含まれる患者個人情報のマスキングと、画像に焼き付けられた
（burned-in）識別情報のマスキングの両方を担当する。
"""

from __future__ import annotations

import copy
import hashlib

import numpy as np

from modules.data_generator import BURN_IN_REGION, Study

MASK_LABEL = "ANONYMIZED"


def _hash_id(patient_id: str) -> str:
    digest = hashlib.sha256(patient_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"ANON-{digest}"


def anonymize_metadata(study: Study) -> Study:
    """患者を特定しうるタグ情報をマスキングしたコピーを返す。"""
    anonymized = copy.copy(study)
    anonymized.patient_name = MASK_LABEL
    anonymized.patient_id = _hash_id(study.patient_id)
    anonymized.birth_date = study.birth_date.replace(month=1, day=1)  # 生年のみ保持
    anonymized.anonymized = True
    return anonymized


def anonymize_slice_image(slice_img: np.ndarray) -> np.ndarray:
    """画像内の焼き付け文字領域を黒塗りしたコピーを返す。"""
    masked = slice_img.copy()
    x0, y0, x1, y1 = BURN_IN_REGION
    masked[y0:y1, x0:x1] = 0
    return masked


def anonymize_study(study: Study) -> Study:
    """タグ・画像の両方を匿名化した検査データのコピーを返す。"""
    anonymized = anonymize_metadata(study)
    anonymized.slices = np.stack(
        [anonymize_slice_image(s) for s in study.slices], axis=0
    )
    return anonymized
