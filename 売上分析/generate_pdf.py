import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, datetime, os

# ── フォント設定（IPAexゴシック） ─────────────────────────
import japanize_matplotlib  # noqa: matplotlib日本語化
_pkg = os.path.dirname(japanize_matplotlib.__file__)
FONT_PATH = os.path.join(_pkg, "fonts", "ipaexg.ttf")
FONT_BOLD = FONT_PATH  # IPAex はウェイト1種類なので同じフォントを使用

pdfmetrics.registerFont(TTFont("HiraKaku",     FONT_PATH))
pdfmetrics.registerFont(TTFont("HiraKakuBold", FONT_BOLD))

matplotlib.rcParams["font.family"] = "IPAexGothic"

# ── データ読み込み ─────────────────────────────────────────
df = pd.read_csv("/Users/m0224/Desktop/ClaudeCode勉強会/売上分析/売上データ.csv")
df["日付"] = pd.to_datetime(df["日付"])
df["月"]   = df["日付"].dt.to_period("M").astype(str)

cat_sales    = df.groupby("カテゴリ")["売上金額"].sum().sort_values(ascending=False)
month_sales  = df.groupby("月")["売上金額"].sum()
person_sales = df.groupby("担当者")["売上金額"].sum().sort_values(ascending=False)
total        = df["売上金額"].sum()

# ── カラーパレット ─────────────────────────────────────────
BLUE      = "#2F5496"
ORANGE    = "#ED7D31"
GREEN     = "#70AD47"
YELLOW    = "#FFC000"
LIGHTBLUE = "#D6E4F7"
BG        = "#EBF3FB"
PALETTE   = [BLUE, ORANGE, GREEN, YELLOW, "#A9D18E", "#FF7F7F"]

# ══════════════════════════════════════════════════════════
# グラフ生成（matplotlibでPNG→reportlabへ埋め込み）
# ══════════════════════════════════════════════════════════
def fig_to_image(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return buf

# ── グラフ①+② 2枚横並び ─────────────────────────────────
fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), facecolor="white")

# 棒グラフ（カテゴリ別）
bars = ax1.bar(cat_sales.index, cat_sales.values,
               color=PALETTE[:len(cat_sales)], width=0.55, edgecolor="white")
ax1.set_title("カテゴリ別売上", fontsize=13, fontweight="bold", color=BLUE, pad=10)
ax1.set_ylabel("売上金額（円）", fontsize=9, color="#555")
ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"¥{int(x):,}"))
ax1.set_facecolor("#FAFCFF")
ax1.spines[["top","right"]].set_visible(False)
ax1.tick_params(axis="x", labelsize=9)
ax1.tick_params(axis="y", labelsize=8)
for bar in bars:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5000,
             f"¥{int(bar.get_height()):,}", ha="center", va="bottom", fontsize=8, color="#333")

# 折れ線グラフ（月別推移）
months = month_sales.index.tolist()
vals   = month_sales.values.tolist()
ax2.plot(months, vals, color=ORANGE, linewidth=2.5, marker="o",
         markersize=8, markerfacecolor="white", markeredgewidth=2.5)
ax2.fill_between(months, vals, alpha=0.12, color=ORANGE)
ax2.set_title("月別売上推移", fontsize=13, fontweight="bold", color=BLUE, pad=10)
ax2.set_ylabel("売上金額（円）", fontsize=9, color="#555")
ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"¥{int(x):,}"))
ax2.set_facecolor("#FAFCFF")
ax2.spines[["top","right"]].set_visible(False)
ax2.tick_params(labelsize=9)
for x, y in zip(months, vals):
    ax2.text(x, y + 8000, f"¥{int(y):,}", ha="center", va="bottom", fontsize=8.5, color="#333")

fig1.tight_layout(pad=2)
img1_buf = fig_to_image(fig1)
plt.close(fig1)

# ── グラフ③+④ 2枚横並び ─────────────────────────────────
fig2, (ax3, ax4) = plt.subplots(1, 2, figsize=(12, 4.5), facecolor="white")

# 円グラフ（カテゴリ構成比）
wedges, texts, autotexts = ax3.pie(
    cat_sales.values,
    labels=cat_sales.index,
    autopct="%1.1f%%",
    colors=PALETTE[:len(cat_sales)],
    startangle=90,
    pctdistance=0.78,
    wedgeprops=dict(width=0.6, edgecolor="white", linewidth=2)
)
for t in texts:
    t.set_fontsize(9)
for at in autotexts:
    at.set_fontsize(8.5)
    at.set_color("white")
    at.set_fontweight("bold")
ax3.set_title("カテゴリ別構成比", fontsize=13, fontweight="bold", color=BLUE, pad=10)

# 横棒グラフ（担当者別）
y_pos = range(len(person_sales))
hbars = ax4.barh(list(person_sales.index), person_sales.values,
                 color=GREEN, height=0.55, edgecolor="white")
ax4.set_title("担当者別売上", fontsize=13, fontweight="bold", color=BLUE, pad=10)
ax4.set_xlabel("売上金額（円）", fontsize=9, color="#555")
ax4.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"¥{int(x):,}"))
ax4.set_facecolor("#FAFCFF")
ax4.spines[["top","right"]].set_visible(False)
ax4.tick_params(labelsize=9)
for bar in hbars:
    ax4.text(bar.get_width() + 2000, bar.get_y() + bar.get_height()/2,
             f"¥{int(bar.get_width()):,}", va="center", fontsize=8, color="#333")

fig2.tight_layout(pad=2)
img2_buf = fig_to_image(fig2)
plt.close(fig2)

# ══════════════════════════════════════════════════════════
# PDF組版
# ══════════════════════════════════════════════════════════
OUT = "/Users/m0224/Desktop/ClaudeCode勉強会/売上分析/売上分析レポート.pdf"

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=18*mm, rightMargin=18*mm,
    topMargin=16*mm, bottomMargin=16*mm
)

W = A4[0] - 36*mm   # 使用可能幅

styles = getSampleStyleSheet()
style_title = ParagraphStyle("title",
    fontName="HiraKakuBold", fontSize=18, textColor=colors.HexColor(BLUE),
    alignment=TA_CENTER, spaceAfter=2)
style_sub = ParagraphStyle("sub",
    fontName="HiraKaku", fontSize=9, textColor=colors.HexColor("#888888"),
    alignment=TA_CENTER, spaceAfter=8)
style_section = ParagraphStyle("section",
    fontName="HiraKakuBold", fontSize=12, textColor=colors.HexColor(BLUE),
    spaceBefore=10, spaceAfter=4)
style_body = ParagraphStyle("body",
    fontName="HiraKaku", fontSize=9, textColor=colors.black, leading=14)
style_footer = ParagraphStyle("footer",
    fontName="HiraKaku", fontSize=7.5, textColor=colors.HexColor("#999"),
    alignment=TA_CENTER)

story = []

# ── タイトルブロック ───────────────────────────────────────
story.append(Paragraph("売上分析レポート", style_title))
story.append(Paragraph(
    f"対象期間：2024年1月〜3月　／　作成日：{datetime.date.today().strftime('%Y年%m月%d日')}",
    style_sub))
story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(BLUE), spaceAfter=8))

# ── KPIサマリー ───────────────────────────────────────────
kpi = [
    ["総売上", f"¥{total:,}"],
    ["取引件数", f"{len(df)} 件"],
    ["1件平均", f"¥{int(df['売上金額'].mean()):,}"],
    ["最高売上月", month_sales.idxmax()],
]
# KPI表：ラベル行＋値行の2行×4列
kpi_flat_label = [Paragraph(k, ParagraphStyle("kl", fontName="HiraKaku", fontSize=8,
                   textColor=colors.HexColor(BLUE), alignment=TA_CENTER)) for k,v in kpi]
kpi_flat_val   = [Paragraph(v, ParagraphStyle("kv", fontName="HiraKakuBold", fontSize=14,
                   textColor=colors.HexColor("#1F3864"), alignment=TA_CENTER)) for k,v in kpi]
kpi_table = Table(
    [kpi_flat_label, kpi_flat_val],
    colWidths=[W/4]*4,
    rowHeights=[9*mm, 13*mm]
)
kpi_table.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor(LIGHTBLUE)),
    ("BACKGROUND", (0,1), (-1,1), colors.HexColor(BG)),
    ("BOX",        (0,0), (-1,-1), 0.5, colors.HexColor("#BFBFBF")),
    ("INNERGRID",  (0,0), (-1,-1), 0.5, colors.HexColor("#BFBFBF")),
    ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ("ALIGN",      (0,0), (-1,-1), "CENTER"),
    ("TOPPADDING", (0,0), (-1,-1), 2),
    ("BOTTOMPADDING",(0,0),(-1,-1), 2),
]))
story.append(kpi_table)
story.append(Spacer(1, 6*mm))

# ── 集計表（カテゴリ別・月別 横並び） ────────────────────
story.append(Paragraph("■ カテゴリ別・月別 売上集計", style_section))

# カテゴリ表データ
cat_data = [["カテゴリ", "売上合計", "構成比"]]
for cat, val in cat_sales.items():
    cat_data.append([cat, f"¥{val:,}", f"{val/total*100:.1f}%"])
cat_data.append(["合計", f"¥{total:,}", "100.0%"])

# 月別表データ
mon_data = [["月", "売上合計", "前月比"]]
prev = None
for mon, val in month_sales.items():
    ratio = f"{val/prev*100:.1f}%" if prev else "—"
    mon_data.append([mon, f"¥{val:,}", ratio])
    prev = val
mon_data.append(["合計", f"¥{month_sales.sum():,}", ""])

half = (W - 6*mm) / 2

def make_summary_table(data, col_widths):
    tbl = Table(data, colWidths=col_widths, rowHeights=7.5*mm)
    ts  = TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  colors.HexColor(BLUE)),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "HiraKakuBold"),
        ("FONTSIZE",      (0,0),  (-1,-1), 8.5),
        ("FONTNAME",      (0,1),  (-1,-2), "HiraKaku"),
        ("FONTNAME",      (0,-1), (-1,-1), "HiraKakuBold"),
        ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#FFF2CC")),
        ("ALIGN",         (0,0),  (0,-1),  "LEFT"),
        ("ALIGN",         (1,0),  (-1,-1), "RIGHT"),
        ("ALIGN",         (0,0),  (-1,0),  "CENTER"),
        ("BOX",           (0,0),  (-1,-1), 0.5, colors.HexColor("#BFBFBF")),
        ("INNERGRID",     (0,0),  (-1,-1), 0.3, colors.HexColor("#BFBFBF")),
        ("ROWBACKGROUNDS",(0,1),  (-1,-2),
         [colors.white, colors.HexColor("#F2F7FE")]),
        ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),  (-1,-1), 5),
        ("RIGHTPADDING",  (0,0),  (-1,-1), 5),
    ])
    tbl.setStyle(ts)
    return tbl

cat_tbl = make_summary_table(cat_data, [half*0.45, half*0.35, half*0.2])
mon_tbl = make_summary_table(mon_data, [half*0.38, half*0.38, half*0.24])

combined = Table([[cat_tbl, "", mon_tbl]],
                 colWidths=[half, 6*mm, half])
combined.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
story.append(combined)
story.append(Spacer(1, 6*mm))

# ── グラフページ ─────────────────────────────────────────
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#BFBFBF"), spaceAfter=4))
story.append(Paragraph("■ 売上グラフ（カテゴリ別・月別推移）", style_section))
story.append(Image(img1_buf, width=W, height=W*4.5/12))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("■ 売上グラフ（構成比・担当者別）", style_section))
story.append(Image(img2_buf, width=W, height=W*4.5/12))

story.append(Spacer(1, 4*mm))
story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
story.append(Spacer(1, 2*mm))
story.append(Paragraph("本レポートはClaudeによって自動生成されました。", style_footer))

# ── ビルド ───────────────────────────────────────────────
doc.build(story)
print(f"保存完了: {OUT}")
