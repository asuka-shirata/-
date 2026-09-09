"""PDFレポート出力モジュール。

匿名化済みの検査情報・代表スライス画像・解析結果を A4 1枚程度に
まとめた PDF を生成する。
"""

from __future__ import annotations

import datetime
import io

import numpy as np
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.data_generator import Study

# 日本語表示のため CID フォント（組み込み）を使用する。
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
_FONT_NAME = "HeiseiKakuGo-W5"


def _array_to_rl_image(image_array: np.ndarray, width_mm: float) -> RLImage:
    pil_img = PILImage.fromarray(image_array)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    aspect = pil_img.height / pil_img.width
    width = width_mm * mm
    height = width * aspect
    return RLImage(buf, width=width, height=height)


def _figure_to_rl_image(fig, width_mm: float) -> RLImage:
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=150)
    buf.seek(0)
    pil_img = PILImage.open(buf)
    width = width_mm * mm
    height = width * (pil_img.height / pil_img.width)
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


def build_pdf_report(
    study: Study,
    representative_slice: np.ndarray,
    size_result: dict,
    density_result: dict,
    density_fig,
    anonymized: bool,
) -> bytes:
    """解析結果をまとめた A4 サイズの PDF レポートをバイト列として生成する。"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleJP", parent=styles["Title"], fontName=_FONT_NAME, fontSize=18
    )
    normal_style = ParagraphStyle(
        "NormalJP", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=9
    )
    heading_style = ParagraphStyle(
        "HeadingJP",
        parent=styles["Heading2"],
        fontName=_FONT_NAME,
        fontSize=12,
        spaceBefore=8,
        spaceAfter=4,
    )

    story = []
    story.append(Paragraph("医療画像解析レポート", title_style))
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "匿名化済み" if anonymized else "未匿名化（社内利用限定）"
    story.append(Paragraph(f"生成日時: {generated_at} / 状態: {status}", normal_style))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("検査情報", heading_style))
    meta_rows = [
        ["検査ID", study.study_id, "患者ID", study.patient_id],
        ["患者氏名", study.patient_name, "性別", study.sex],
        ["生年月日", study.birth_date.isoformat(), "撮影日", study.study_date.isoformat()],
        ["モダリティ", study.modality, "部位", study.body_part],
        ["総スライス数", str(study.total_slice_count), "画素間隔", f"{study.pixel_spacing_mm} mm"],
    ]
    meta_table = Table(meta_rows, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("代表スライス画像", heading_style))
    story.append(_array_to_rl_image(representative_slice, width_mm=70))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("解析結果（大きさ計測）", heading_style))
    size_rows = [
        ["面積 (px)", str(size_result["area_px"]), "面積 (mm²)", str(size_result["area_mm2"])],
        ["推定径 (mm)", str(size_result["estimated_diameter_mm"]), "しきい値", str(size_result["threshold"])],
    ]
    size_table = Table(size_rows, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    size_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(size_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("解析結果（濃度解析）", heading_style))
    density_rows = [
        ["平均輝度", str(density_result["mean_intensity"]), "標準偏差", str(density_result["std_intensity"])],
        ["最小値", str(density_result["min_intensity"]), "最大値", str(density_result["max_intensity"])],
    ]
    density_table = Table(density_rows, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    density_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(density_table)
    story.append(Spacer(1, 4 * mm))
    story.append(_figure_to_rl_image(density_fig, width_mm=90))

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "※本レポートはデモ版であり、解析数値はプレースホルダーです。臨床判断には使用できません。",
            normal_style,
        )
    )

    doc.build(story)
    return buf.getvalue()
