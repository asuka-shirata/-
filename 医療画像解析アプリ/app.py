"""医療画像解析アプリ（デモ / プロトタイプ）

CT・MRI画像のようなダミー医療画像データを読み込み、付帯情報（タグ）の
確認・修正、画像解析（大きさ計測・濃度解析）、匿名化、PDFレポート出力を
一通り試せる社内利用向けStreamlitアプリ。
"""

from __future__ import annotations

import datetime

import streamlit as st

from modules import analysis, anonymizer, report
from modules.data_generator import BODY_PARTS, MODALITIES, SEX_OPTIONS, generate_dummy_dataset

st.set_page_config(page_title="医療画像解析アプリ（デモ）", layout="wide")

if "studies" not in st.session_state:
    st.session_state.studies = []
if "selected_study_id" not in st.session_state:
    st.session_state.selected_study_id = None
if "slice_index" not in st.session_state:
    st.session_state.slice_index = 0


def get_selected_study():
    for study in st.session_state.studies:
        if study.study_id == st.session_state.selected_study_id:
            return study
    return None


def get_display_study(study):
    """サイドバーの匿名化トグルに応じて、表示用の（必要なら匿名化済み）検査データを返す。"""
    if study is None:
        return None
    if st.session_state.get("global_anonymize", False):
        return anonymizer.anonymize_study(study)
    return study


# ── サイドバー：データ生成・選択・匿名化トグル ──────────────────────────
with st.sidebar:
    st.header("① データ読み込み")
    num_cases = st.number_input("生成する件数", min_value=10, max_value=20, value=12, step=1)
    seed_input = st.text_input("乱数シード（任意）", value="")
    if st.button("ダミーデータを生成", use_container_width=True):
        seed = int(seed_input) if seed_input.strip().isdigit() else None
        with st.spinner("ダミー画像データを生成中..."):
            st.session_state.studies = generate_dummy_dataset(int(num_cases), seed=seed)
        st.session_state.selected_study_id = st.session_state.studies[0].study_id
        st.session_state.slice_index = 0
        st.success(f"{num_cases} 件のダミー検査データを生成しました。")

    st.divider()

    if st.session_state.studies:
        study_ids = [s.study_id for s in st.session_state.studies]
        current = st.session_state.selected_study_id or study_ids[0]
        selected = st.selectbox("対象検査を選択", study_ids, index=study_ids.index(current))
        if selected != st.session_state.selected_study_id:
            st.session_state.selected_study_id = selected
            st.session_state.slice_index = 0

        st.divider()
        st.header("④ 匿名化")
        st.toggle(
            "個人情報を匿名化して表示",
            key="global_anonymize",
            help="ONにすると患者氏名・患者ID・生年月日および画像内の焼き付け文字がマスキングされます。",
        )
    else:
        st.info("まずダミーデータを生成してください。")


st.title("🏥 医療画像解析アプリ（デモ / プロトタイプ）")
st.caption("※本アプリはデモ版です。表示されるデータ・解析結果はすべてダミーです。")

if not st.session_state.studies:
    st.stop()

tab_list, tab_viewer, tab_analysis, tab_anonymize, tab_report = st.tabs(
    ["① データ一覧", "② 画像表示・タグ編集", "③ 画像解析", "④ 匿名化プレビュー", "⑤ レポート出力"]
)

# ── ① データ一覧 ────────────────────────────────────────────────
with tab_list:
    st.subheader("読み込み済み検査データ一覧")
    rows = []
    for study in st.session_state.studies:
        display = get_display_study(study)
        rows.append(
            {
                "検査ID": display.study_id,
                "患者ID": display.patient_id,
                "患者氏名": display.patient_name,
                "性別": display.sex,
                "生年月日": display.birth_date.isoformat(),
                "モダリティ": display.modality,
                "部位": display.body_part,
                "撮影日": display.study_date.isoformat(),
                "総スライス数": display.total_slice_count,
                "読込済スライス数": len(display.slices),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        f"デモのため、実際に読み込む画像は1件あたり最大 "
        f"{st.session_state.studies[0].slices.shape[0] if st.session_state.studies else 0} 枚程度に制限しています。"
    )

# ── ② 画像表示・タグ編集 ─────────────────────────────────────────
with tab_viewer:
    study = get_selected_study()
    if study is None:
        st.warning("検査データが選択されていません。")
    else:
        display_study = get_display_study(study)
        col_img, col_tags = st.columns([3, 2])

        with col_img:
            st.subheader(f"画像表示: {display_study.study_id}")
            max_idx = len(display_study.slices) - 1
            slice_index = st.slider(
                "スライス位置", min_value=0, max_value=max_idx, value=min(st.session_state.slice_index, max_idx)
            )
            st.session_state.slice_index = slice_index
            st.image(
                display_study.slices[slice_index],
                caption=f"スライス {slice_index + 1} / {len(display_study.slices)}",
                use_container_width=True,
            )

        with col_tags:
            st.subheader("付帯情報（タグ）の確認・修正")
            if st.session_state.get("global_anonymize", False):
                st.info("匿名化表示中のため、編集は元データに対して行われます。")
            with st.form("tag_edit_form"):
                patient_name = st.text_input("患者氏名", value=study.patient_name)
                patient_id = st.text_input("患者ID", value=study.patient_id)
                birth_date = st.date_input(
                    "生年月日",
                    value=study.birth_date,
                    min_value=datetime.date(1900, 1, 1),
                    max_value=datetime.date.today(),
                )
                sex = st.selectbox("性別", SEX_OPTIONS, index=SEX_OPTIONS.index(study.sex))
                modality = st.selectbox("モダリティ", MODALITIES, index=MODALITIES.index(study.modality))
                body_part = st.selectbox("部位", BODY_PARTS, index=BODY_PARTS.index(study.body_part))
                study_date = st.date_input("撮影日", value=study.study_date)
                notes = st.text_area("備考", value=study.notes)

                submitted = st.form_submit_button("保存", use_container_width=True)
                if submitted:
                    study.patient_name = patient_name
                    study.patient_id = patient_id
                    study.birth_date = birth_date
                    study.sex = sex
                    study.modality = modality
                    study.body_part = body_part
                    study.study_date = study_date
                    study.notes = notes
                    st.success("付帯情報を更新しました。")

# ── ③ 画像解析 ──────────────────────────────────────────────────
with tab_analysis:
    study = get_selected_study()
    if study is None:
        st.warning("検査データが選択されていません。")
    else:
        display_study = get_display_study(study)
        st.subheader(f"画像解析: {display_study.study_id}")
        st.caption("※解析結果はデモ用のプレースホルダー処理による簡易計算値です。")

        max_idx = len(display_study.slices) - 1
        slice_index = st.slider(
            "解析対象スライス", min_value=0, max_value=max_idx, value=min(st.session_state.slice_index, max_idx), key="analysis_slice"
        )
        threshold = st.slider("大きさ計測しきい値（輝度）", min_value=0, max_value=255, value=analysis.DEFAULT_INTENSITY_THRESHOLD)

        target_slice = display_study.slices[slice_index]
        col_img, col_result = st.columns([2, 3])

        with col_img:
            st.image(target_slice, caption=f"スライス {slice_index + 1}", use_container_width=True)

        with col_result:
            size_result = analysis.measure_size(
                target_slice, pixel_spacing_mm=display_study.pixel_spacing_mm, threshold=threshold
            )
            density_result = analysis.analyze_density(target_slice)

            st.markdown("**大きさの計測**")
            m1, m2, m3 = st.columns(3)
            m1.metric("面積 (mm²)", size_result["area_mm2"])
            m2.metric("推定径 (mm)", size_result["estimated_diameter_mm"])
            m3.metric("面積 (px)", size_result["area_px"])

            st.markdown("**濃度解析**")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("平均輝度", density_result["mean_intensity"])
            d2.metric("標準偏差", density_result["std_intensity"])
            d3.metric("最小値", density_result["min_intensity"])
            d4.metric("最大値", density_result["max_intensity"])

            fig = analysis.build_density_histogram_figure(target_slice)
            st.pyplot(fig, use_container_width=True)

        # レポート出力タブで再利用するために解析結果をキャッシュ
        st.session_state["last_analysis"] = {
            "study_id": display_study.study_id,
            "slice_index": slice_index,
            "size_result": size_result,
            "density_result": density_result,
        }

# ── ④ 匿名化プレビュー ────────────────────────────────────────────
with tab_anonymize:
    study = get_selected_study()
    if study is None:
        st.warning("検査データが選択されていません。")
    else:
        st.subheader("匿名化プレビュー（元データ vs 匿名化後）")
        st.caption("サイドバーの「個人情報を匿名化して表示」トグルはアプリ全体の表示に反映されます。ここでは比較のため両方を並べて表示します。")

        anonymized_study = anonymizer.anonymize_study(study)
        max_idx = len(study.slices) - 1
        preview_index = min(st.session_state.slice_index, max_idx)

        col_before, col_after = st.columns(2)
        with col_before:
            st.markdown("**匿名化前**")
            st.image(study.slices[preview_index], use_container_width=True)
            st.table(
                {
                    "項目": ["患者氏名", "患者ID", "生年月日"],
                    "値": [study.patient_name, study.patient_id, study.birth_date.isoformat()],
                }
            )
        with col_after:
            st.markdown("**匿名化後**")
            st.image(anonymized_study.slices[preview_index], use_container_width=True)
            st.table(
                {
                    "項目": ["患者氏名", "患者ID", "生年月日"],
                    "値": [
                        anonymized_study.patient_name,
                        anonymized_study.patient_id,
                        anonymized_study.birth_date.isoformat(),
                    ],
                }
            )

# ── ⑤ レポート出力 ────────────────────────────────────────────────
with tab_report:
    study = get_selected_study()
    if study is None:
        st.warning("検査データが選択されていません。")
    else:
        st.subheader(f"PDFレポート出力: {study.study_id}")
        anonymize_report = st.checkbox("匿名化した状態でレポートを出力する（推奨）", value=True)
        max_idx = len(study.slices) - 1
        representative_index = st.slider(
            "レポートに掲載する代表スライス",
            min_value=0,
            max_value=max_idx,
            value=max_idx // 2,
        )

        report_study = anonymizer.anonymize_study(study) if anonymize_report else study
        representative_slice = report_study.slices[representative_index]

        size_result = analysis.measure_size(representative_slice, pixel_spacing_mm=report_study.pixel_spacing_mm)
        density_result = analysis.analyze_density(representative_slice)

        st.markdown("**レポートに含まれる内容のプレビュー**")
        col_img, col_meta = st.columns([1, 2])
        with col_img:
            st.image(representative_slice, use_container_width=True)
        with col_meta:
            st.write(
                {
                    "検査ID": report_study.study_id,
                    "患者氏名": report_study.patient_name,
                    "患者ID": report_study.patient_id,
                    "モダリティ": report_study.modality,
                    "部位": report_study.body_part,
                }
            )
            st.write({"面積(mm²)": size_result["area_mm2"], "推定径(mm)": size_result["estimated_diameter_mm"]})
            st.write({"平均輝度": density_result["mean_intensity"], "標準偏差": density_result["std_intensity"]})

        if st.button("PDFレポートを生成", type="primary"):
            fig = analysis.build_density_histogram_figure(representative_slice)
            pdf_bytes = report.build_pdf_report(
                study=report_study,
                representative_slice=representative_slice,
                size_result=size_result,
                density_result=density_result,
                density_fig=fig,
                anonymized=anonymize_report,
            )
            st.session_state["pdf_bytes"] = pdf_bytes
            st.session_state["pdf_filename"] = f"{report_study.study_id}_report.pdf"
            st.success("PDFレポートを生成しました。下のボタンからダウンロードできます。")

        if st.session_state.get("pdf_bytes"):
            st.download_button(
                "PDFをダウンロード",
                data=st.session_state["pdf_bytes"],
                file_name=st.session_state.get("pdf_filename", "report.pdf"),
                mime="application/pdf",
            )
