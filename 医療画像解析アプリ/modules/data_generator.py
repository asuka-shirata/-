"""デモ用ダミー医療画像・付帯情報の生成モジュール。

実データが無くてもアプリを試せるように、CT/MRIスライス画像に見立てた
合成画像と、DICOMタグを模した付帯情報（患者名・患者ID・撮影日等）を
その場で生成する。
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

# デモ用に生成する実スライス枚数の上限（メモリ・表示速度のため）。
# 「1件あたり数百枚」を想定した total_slice_count はメタデータとして保持しつつ、
# 実際にロードする画像枚数はこの上限で間引く。
MAX_DEMO_SLICES = 40
IMAGE_SIZE = 256

MODALITIES = ["CT", "MRI"]
BODY_PARTS = ["胸部", "腹部", "頭部", "骨盤"]
SEX_OPTIONS = ["M", "F"]

_SURNAMES = ["山田", "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "中村", "小林", "加藤"]
_GIVEN_NAMES_M = ["太郎", "健一", "翔太", "大輔", "拓也"]
_GIVEN_NAMES_F = ["花子", "美咲", "さくら", "由美", "陽子"]

# 画像左上に焼き付け文字（burned-in annotation）を模したテキストを描画する領域。
# 匿名化処理はこの領域を黒塗りする。
BURN_IN_REGION = (4, 4, 160, 22)  # (x0, y0, x1, y1)


@dataclass
class Study:
    """1件の検査データ（患者情報 + スライス画像群）を表す。"""

    study_id: str
    patient_id: str
    patient_name: str
    birth_date: datetime.date
    sex: str
    modality: str
    body_part: str
    study_date: datetime.date
    total_slice_count: int
    pixel_spacing_mm: float
    slices: np.ndarray  # shape: (n, H, W), dtype=uint8
    notes: str = ""
    anonymized: bool = field(default=False)


def _random_date(rng: random.Random, start_year: int, end_year: int) -> datetime.date:
    start = datetime.date(start_year, 1, 1)
    end = datetime.date(end_year, 12, 31)
    delta_days = (end - start).days
    return start + datetime.timedelta(days=rng.randint(0, delta_days))


def _generate_patient_name(rng: random.Random, sex: str) -> str:
    surname = rng.choice(_SURNAMES)
    given = rng.choice(_GIVEN_NAMES_M if sex == "M" else _GIVEN_NAMES_F)
    return f"{surname} {given}"


def _generate_phantom_slice(rng: random.Random, slice_ratio: float) -> np.ndarray:
    """円形の「体軸断面」と楕円の「病変候補」を含む合成グレースケール画像を生成する。

    slice_ratio: 0.0〜1.0 の値。スライス位置に応じて病変の大きさが
    連続的に変化するように用いる（3Dの塊をスライスした見た目を模す）。
    """
    size = IMAGE_SIZE
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size / 2, size / 2

    # 背景の「体」（円形の組織領域）
    body_radius = size * 0.4
    body_dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    background = np.clip(120 + rng.uniform(-10, 10) - body_dist * 0.15, 0, 255)
    image = np.where(body_dist < body_radius, background, 20.0)

    # 病変候補（楕円）。スライス位置に応じてサイズが山型に変化する。
    lesion_profile = np.sin(np.pi * slice_ratio)  # 中央スライス付近で最大
    lesion_radius = size * (0.03 + 0.12 * lesion_profile)
    lesion_cx = cx + size * 0.1
    lesion_cy = cy - size * 0.05
    lesion_dist = np.sqrt((xx - lesion_cx) ** 2 + (yy - lesion_cy) ** 2)
    lesion_mask = lesion_dist < lesion_radius
    image = np.where(lesion_mask, 200 + rng.uniform(-5, 5), image)

    # ノイズ付与
    noise = rng.gauss(0, 1) * np.random.default_rng(rng.randint(0, 1_000_000)).normal(
        0, 6, size=(size, size)
    )
    image = np.clip(image + noise, 0, 255).astype(np.uint8)

    pil_img = Image.fromarray(image, mode="L").convert("RGB")
    draw = ImageDraw.Draw(pil_img)
    draw.rectangle(BURN_IN_REGION, fill=(0, 0, 0))
    return np.array(pil_img)


def _burn_in_text(image_rgb: np.ndarray, text: str) -> np.ndarray:
    pil_img = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_img)
    draw.rectangle(BURN_IN_REGION, fill=(0, 0, 0))
    draw.text((BURN_IN_REGION[0] + 2, BURN_IN_REGION[1] + 2), text, fill=(255, 255, 0))
    return np.array(pil_img)


def generate_study(index: int, rng: random.Random) -> Study:
    sex = rng.choice(SEX_OPTIONS)
    modality = rng.choice(MODALITIES)
    patient_name = _generate_patient_name(rng, sex)
    total_slice_count = rng.randint(80, 320)
    loaded_slice_count = min(total_slice_count, MAX_DEMO_SLICES)

    slices = []
    for i in range(loaded_slice_count):
        ratio = i / max(loaded_slice_count - 1, 1)
        slice_img = _generate_phantom_slice(rng, ratio)
        slice_img = _burn_in_text(slice_img, patient_name)
        slices.append(slice_img)

    return Study(
        study_id=f"STU-{index + 1:04d}",
        patient_id=f"P{rng.randint(100000, 999999)}",
        patient_name=patient_name,
        birth_date=_random_date(rng, 1940, 2010),
        sex=sex,
        modality=modality,
        body_part=rng.choice(BODY_PARTS),
        study_date=_random_date(rng, 2023, 2026),
        total_slice_count=total_slice_count,
        pixel_spacing_mm=round(rng.uniform(0.5, 1.2), 2),
        slices=np.stack(slices, axis=0),
        notes="",
    )


def generate_dummy_dataset(num_cases: int, seed: int | None = None) -> list[Study]:
    """指定件数分のダミー検査データセットを生成する。"""
    rng = random.Random(seed)
    return [generate_study(i, rng) for i in range(num_cases)]
