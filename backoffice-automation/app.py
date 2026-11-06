# =============================================================================
# バックオフィス業務自動化デモアプリ
#
# このアプリでできること：
#   機能1：勤怠CSVから、残業代と総支給額を自動で計算する
#   機能2：銀行明細CSVの摘要から、勘定科目を推論して仕訳データを作る
#
# 起動方法（くわしくは README.md を見てください）：
#   streamlit run app.py
#
# 【ご注意】これはデモです。所得税・社会保険料の控除や消費税の区分は扱いません。
#           実際の業務に使う前に、計算結果を必ず担当者や専門家が確認してください。
# =============================================================================

# ここで、アプリに必要な道具（ライブラリ）を読み込んでいます
import io  # アップロードされたデータをファイルのように扱うための道具
import math  # 端数処理（切り捨てなど）に使う道具
import unicodedata  # 全角・半角の違いをそろえるための道具
from pathlib import Path  # ファイルの場所を扱うための道具

import pandas as pd  # 表データ（Excelのような表）を扱うための道具
import streamlit as st  # ブラウザの画面を作るための道具


# =============================================================================
# 設定値（会社のルールに合わせて変更しやすいよう、ここにまとめています）
# =============================================================================

# このファイルと同じ場所にある、お試し用CSVの場所
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PAYROLL_PATH = BASE_DIR / "sample-payroll.csv"
SAMPLE_BANK_PATH = BASE_DIR / "sample-bank.csv"

# 勤怠CSVに必ず必要な列の名前
PAYROLL_REQUIRED_COLUMNS = ["従業員名", "基本給", "所定労働時間", "実労働時間", "残業時間"]

# 銀行明細CSVに必ず必要な列の名前
BANK_REQUIRED_COLUMNS = ["日付", "入出金区分", "金額", "摘要"]

# 残業代の割増率の初期値（法律で定められた最低ラインは25%増 = 1.25倍）
DEFAULT_OVERTIME_RATE = 1.25

# 月60時間を超えた残業の割増率の初期値（法律で定められた最低ラインは50%増 = 1.5倍）
DEFAULT_OVER_60H_RATE = 1.5
OVER_60H_THRESHOLD = 60

# 「手作業なら1件あたり何分かかるか」の仮定（削減効果の目安を出すためだけに使います）
MANUAL_MINUTES_PER_EMPLOYEE = 5
MANUAL_MINUTES_PER_TRANSACTION = 2

# 預金口座を表す勘定科目（仕訳の相手側に使います）
BANK_ACCOUNT_NAME = "普通預金"

# キーワードに当てはまらなかった取引に、ひとまず付ける勘定科目
UNMATCHED_DEPOSIT_ACCOUNT = "仮受金"  # 入金の場合
UNMATCHED_WITHDRAWAL_ACCOUNT = "仮払金"  # 出金の場合

# 勘定科目を推論するためのルール表です。
# 【重要】上から順番に調べて、最初に当てはまったルールを採用します。
# そのため「東京電力株式会社」が水道光熱費になるよう、会社名の共通ルール
# （株式会社）は一番下に置いています。
DEFAULT_RULES = [
    # --- 人件費・税金など ---
    {"キーワード": "給与", "入出金区分": "出金", "勘定科目": "給料手当"},
    {"キーワード": "年金事務所", "入出金区分": "出金", "勘定科目": "法定福利費"},
    {"キーワード": "税務署", "入出金区分": "出金", "勘定科目": "租税公課"},
    # --- 銀行関連 ---
    {"キーワード": "手数料", "入出金区分": "出金", "勘定科目": "支払手数料"},
    {"キーワード": "利息", "入出金区分": "入金", "勘定科目": "受取利息"},
    # --- 水道光熱費 ---
    {"キーワード": "電気", "入出金区分": "出金", "勘定科目": "水道光熱費"},
    {"キーワード": "デンキ", "入出金区分": "出金", "勘定科目": "水道光熱費"},
    {"キーワード": "電力", "入出金区分": "出金", "勘定科目": "水道光熱費"},
    {"キーワード": "東京ガス", "入出金区分": "出金", "勘定科目": "水道光熱費"},
    {"キーワード": "水道", "入出金区分": "出金", "勘定科目": "水道光熱費"},
    # --- 旅費交通費 ---
    {"キーワード": "JR", "入出金区分": "出金", "勘定科目": "旅費交通費"},
    {"キーワード": "鉄道", "入出金区分": "出金", "勘定科目": "旅費交通費"},
    {"キーワード": "交通", "入出金区分": "出金", "勘定科目": "旅費交通費"},
    {"キーワード": "タクシー", "入出金区分": "出金", "勘定科目": "旅費交通費"},
    # --- 通信費（AWSは名前に「Amazon」を含むので、Amazonより上に置きます） ---
    {"キーワード": "NTT", "入出金区分": "出金", "勘定科目": "通信費"},
    {"キーワード": "AWS", "入出金区分": "出金", "勘定科目": "通信費"},
    {"キーワード": "AMAZON WEB SERVICES", "入出金区分": "出金", "勘定科目": "通信費"},
    # --- 消耗品費 ---
    {"キーワード": "Amazon", "入出金区分": "出金", "勘定科目": "消耗品費"},
    {"キーワード": "アスクル", "入出金区分": "出金", "勘定科目": "消耗品費"},
    # --- 地代家賃 ---
    {"キーワード": "家賃", "入出金区分": "出金", "勘定科目": "地代家賃"},
    # --- 会社名の共通ルール（他のどれにも当てはまらなかった場合） ---
    # 銀行明細では株式会社が「ｶ)」「(ｶ」と略されることが多いので、それも含めます
    {"キーワード": "株式会社", "入出金区分": "入金", "勘定科目": "売上高"},
    {"キーワード": "カ)", "入出金区分": "入金", "勘定科目": "売上高"},
    {"キーワード": "(カ", "入出金区分": "入金", "勘定科目": "売上高"},
    {"キーワード": "株式会社", "入出金区分": "出金", "勘定科目": "外注費"},
    {"キーワード": "カ)", "入出金区分": "出金", "勘定科目": "外注費"},
    {"キーワード": "(カ", "入出金区分": "出金", "勘定科目": "外注費"},
]


# =============================================================================
# 共通で使う小さな処理
# =============================================================================


def normalize_text(text):
    """全角・半角や大文字・小文字の違いをそろえます（例：ﾃﾞﾝｷ → デンキ、ａｍａｚｏｎ → AMAZON）。"""
    return unicodedata.normalize("NFKC", str(text)).upper().strip()


def round_half_up(value):
    """小数点以下を四捨五入して、円単位の整数にします。"""
    return int(math.floor(value + 0.5))


def to_number(series):
    """「1,000円」のような文字を計算できる数字に変えます。変換できないものは空欄になります。"""
    cleaned = (
        series.astype(str)
        .map(lambda value: unicodedata.normalize("NFKC", value))
        .str.replace(r"[,¥円\s]", "", regex=True)
    )
    numbers = pd.to_numeric(cleaned, errors="coerce")
    # 「inf」のように数字として読めても金額にならない値（無限大）は、空欄として扱います
    return numbers.where(numbers.abs() != float("inf"))


def read_csv_bytes(csv_bytes):
    """CSVデータを表に読み込みます。文字コードはUTF-8とShift_JISのどちらにも対応します。"""
    # 勤怠システムや銀行のCSVはShift_JISのことが多いので、順番に試して読み込みます
    for encoding in ("utf-8-sig", "cp932"):
        try:
            # ここでCSVデータを読み込んでいます（勝手に形が変わらないよう、まず文字として読みます）
            table = pd.read_csv(
                io.BytesIO(csv_bytes),
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
            )
        except UnicodeDecodeError:
            continue  # この文字コードでは読めなかったので、次の文字コードを試します

        # 列名とデータの前後にある余分な空白を取り除きます
        table.columns = [str(column).strip() for column in table.columns]
        table = table.apply(lambda column: column.str.strip())

        # Excelで保存した時にできる「全部空欄の行」を取り除きます
        return table[(table != "").any(axis=1)].copy()

    raise ValueError("文字コードを判別できませんでした。UTF-8かShift_JISで保存してください。")


def to_csv_bytes(table, encoding):
    """表をダウンロード用のCSVデータに変換します。"""
    return table.to_csv(index=False).encode(encoding)


def load_input_csv(label, sample_path, key):
    """CSVのアップロード欄を表示して、読み込んだ表を返します（まだ無ければ None を返します）。"""
    uploaded_file = st.file_uploader(label, type="csv", key=f"{key}_uploader")

    csv_bytes = None
    if uploaded_file is not None:
        # アップロードされたファイルを優先して使います
        csv_bytes = uploaded_file.getvalue()
    elif sample_path.exists() and st.checkbox(
        "手元にCSVがないので、サンプルデータで試す", key=f"{key}_sample"
    ):
        csv_bytes = sample_path.read_bytes()

    if csv_bytes is None:
        return None

    # 読み込みに失敗しても画面が止まらないよう、分かりやすいメッセージを表示します
    try:
        return read_csv_bytes(csv_bytes)
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        st.error(f"CSVを読み込めませんでした。ファイルの中身を確認してください。（{error}）")
        return None


def find_missing_columns(table, required_columns):
    """必要な列のうち、CSVに存在しない列の一覧を返します。"""
    return [column for column in required_columns if column not in table.columns]


def show_error_list(title, errors):
    """入力データの間違いを、行番号つきで画面に表示します。"""
    st.error(f"{title}（{len(errors)}件）\n\n" + "\n".join(f"- {error}" for error in errors))


def show_download_button(table, file_name, key):
    """CSVのダウンロードボタンを、文字コードの選択欄と一緒に表示します。"""
    encoding_label = st.radio(
        "CSVの文字コード（取り込み先のソフトに合わせて選びます）",
        ["UTF-8（BOM付き）", "Shift_JIS"],
        horizontal=True,
        key=f"{key}_encoding",
    )
    encoding = "utf-8-sig" if encoding_label.startswith("UTF-8") else "cp932"

    try:
        csv_bytes = to_csv_bytes(table, encoding)
    except UnicodeEncodeError:
        # Shift_JISで表せない文字があると、文字が欠けたまま出力される恐れがあるので止めます
        st.error("Shift_JISで表せない文字が含まれています。「UTF-8（BOM付き）」を選んでください。")
        return

    st.download_button(
        label="📥 CSVをダウンロード",
        data=csv_bytes,
        file_name=file_name,
        mime="text/csv",
        type="primary",
        key=f"{key}_download",
    )


def show_time_saving(count, minutes_per_item, unit):
    """手作業と比べて、どれくらい時間を減らせるかの目安を表示します。"""
    st.info(
        f"⏱️ 削減効果の目安：手作業なら約 **{count * minutes_per_item} 分**"
        f"（1{unit}あたり{minutes_per_item}分と仮定）かかる作業が、数秒で終わりました。"
    )


# =============================================================================
# 機能1：給与計算の自動化
# =============================================================================


def validate_payroll(table):
    """勤怠データの中に、計算できない値がないかを調べます。"""
    errors = []

    for row_number, (index, row) in enumerate(table.iterrows(), start=1):
        if row["従業員名"] == "":
            errors.append(f"{row_number}行目：従業員名が空欄です")

        for column in PAYROLL_REQUIRED_COLUMNS[1:]:
            value = row[f"{column}_数値"]
            if pd.isna(value):
                errors.append(f"{row_number}行目：{column}「{row[column]}」が数字ではありません")
            elif value < 0:
                errors.append(f"{row_number}行目：{column}がマイナスになっています")

        # 所定労働時間が0だと、時間単価の計算（0で割る計算）ができません
        if row["所定労働時間_数値"] == 0:
            errors.append(f"{row_number}行目：所定労働時間が0です")

        if row["実労働時間_数値"] < row["残業時間_数値"]:
            errors.append(f"{row_number}行目：残業時間が実労働時間より多くなっています")

    return errors


def calculate_payroll(table, overtime_rate, over_60h_rate):
    """1人ずつ、残業代と総支給額を計算します。"""
    results = []

    # ここで従業員を1人ずつ順番に計算しています
    for index, row in table.iterrows():
        base_salary = row["基本給_数値"]
        scheduled_hours = row["所定労働時間_数値"]
        actual_hours = row["実労働時間_数値"]
        overtime_hours = row["残業時間_数値"]
        commuting_allowance = row["通勤手当_数値"]

        # 1時間あたりの給与（時間単価）＝ 基本給 ÷ 所定労働時間
        hourly_wage = base_salary / scheduled_hours

        # 残業時間を「60時間まで」と「60時間を超えた分」に分けます
        normal_overtime = min(overtime_hours, OVER_60H_THRESHOLD)
        over_60h_overtime = max(overtime_hours - OVER_60H_THRESHOLD, 0)

        # 残業代 ＝ 時間単価 ×（60時間までの残業 × 割増率 ＋ 60時間超の残業 × 割増率）
        overtime_pay = round_half_up(
            hourly_wage * (normal_overtime * overtime_rate + over_60h_overtime * over_60h_rate)
        )

        # 所定内に働いた時間 ＝ 実労働時間 − 残業時間
        worked_within_schedule = actual_hours - overtime_hours

        # 所定労働時間に足りない分は、欠勤・遅刻などとして差し引きます
        shortage_hours = max(scheduled_hours - worked_within_schedule, 0)
        absence_deduction = round_half_up(hourly_wage * shortage_hours)

        # 総支給額 ＝ 基本給 ＋ 通勤手当 ＋ 残業代 − 欠勤控除
        total_pay = round_half_up(
            base_salary + commuting_allowance + overtime_pay - absence_deduction
        )

        # 自動では判断せず、人の目で確認してほしい内容を書き出します
        notes = []
        if shortage_hours > 0:
            notes.append(f"所定に{shortage_hours:g}時間不足（欠勤控除あり）")
        if worked_within_schedule > scheduled_hours:
            over_hours = worked_within_schedule - scheduled_hours
            notes.append(f"残業に未計上の労働が{over_hours:g}時間ある可能性")
        if overtime_hours > OVER_60H_THRESHOLD:
            notes.append("月60時間超の残業あり")

        results.append(
            {
                "従業員名": row["従業員名"],
                "基本給": round_half_up(base_salary),
                "通勤手当": round_half_up(commuting_allowance),
                "時間単価": round(hourly_wage, 2),
                "残業時間": overtime_hours,
                "残業代": overtime_pay,
                "欠勤控除": absence_deduction,
                "総支給額": total_pay,
                "確認事項": " / ".join(notes),
            }
        )

    return pd.DataFrame(results)


def show_payroll_page():
    """機能1の画面を表示します。"""
    st.header("💰 給与計算の自動化")
    st.write("勤怠データのCSVをアップロードするだけで、残業代と総支給額を自動で計算します。")

    # --- ステップ1：CSVの読み込み ---
    st.subheader("ステップ1：勤怠データを読み込む")
    st.caption("必要な列：" + "、".join(PAYROLL_REQUIRED_COLUMNS) + "（通勤手当は任意）")
    table = load_input_csv("勤怠CSVをアップロード", SAMPLE_PAYROLL_PATH, "payroll")

    # まだCSVが読み込まれていなければ、ここで処理を終わります
    if table is None:
        return

    # 必要な列がそろっているかを確認します
    missing_columns = find_missing_columns(table, PAYROLL_REQUIRED_COLUMNS)
    if missing_columns:
        st.error("CSVに次の列が見つかりません：" + "、".join(missing_columns))
        return

    # 数字の列を、計算できる形に変換します
    for column in PAYROLL_REQUIRED_COLUMNS[1:]:
        table[f"{column}_数値"] = to_number(table[column])

    # 通勤手当は任意の列なので、無い場合や空欄の場合は0円として扱います
    if "通勤手当" not in table.columns:
        table["通勤手当"] = "0"
    table["通勤手当"] = table["通勤手当"].replace("", "0")
    table["通勤手当_数値"] = to_number(table["通勤手当"])

    # 間違ったデータで給与を計算しないよう、問題があればここで止めます
    errors = validate_payroll(table)
    invalid_allowance = table["通勤手当_数値"].isna() | (table["通勤手当_数値"] < 0)
    for row_number, is_invalid in enumerate(invalid_allowance, start=1):
        if is_invalid:
            errors.append(f"{row_number}行目：通勤手当が正しい金額ではありません")
    if errors:
        show_error_list("データに修正が必要な箇所があります", errors)
        return

    with st.expander("読み込んだデータを確認する"):
        st.dataframe(table[PAYROLL_REQUIRED_COLUMNS + ["通勤手当"]], hide_index=True)

    # --- ステップ2：計算ルールの設定 ---
    st.subheader("ステップ2：計算ルールを確認する")
    left_column, right_column = st.columns(2)
    overtime_rate = left_column.number_input(
        "残業の割増率（月60時間まで）",
        min_value=DEFAULT_OVERTIME_RATE,
        value=DEFAULT_OVERTIME_RATE,
        step=0.05,
        help="法定の最低ラインは1.25倍です。",
    )
    over_60h_rate = right_column.number_input(
        "残業の割増率（月60時間超）",
        min_value=DEFAULT_OVER_60H_RATE,
        value=DEFAULT_OVER_60H_RATE,
        step=0.05,
        help="法定の最低ラインは1.5倍です。",
    )
    st.caption(
        "残業代 ＝ 基本給 ÷ 所定労働時間 × 残業時間 × 割増率 ／ "
        "総支給額 ＝ 基本給 ＋ 通勤手当 ＋ 残業代 − 欠勤控除"
    )

    # --- ステップ3：計算結果の表示 ---
    st.subheader("ステップ3：計算結果を確認する")
    result = calculate_payroll(table, overtime_rate, over_60h_rate)

    # 合計の数字を、大きく見やすく表示します
    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("対象人数", f"{len(result)} 人")
    metric_2.metric("残業代の合計", f"{result['残業代'].sum():,} 円")
    metric_3.metric("総支給額の合計", f"{result['総支給額'].sum():,} 円")

    show_time_saving(len(result), MANUAL_MINUTES_PER_EMPLOYEE, "人")

    # ここで計算結果の表を画面に表示しています
    st.dataframe(result, hide_index=True)

    # 確認が必要な人がいれば、見落とさないようにお知らせします
    check_count = int((result["確認事項"] != "").sum())
    if check_count > 0:
        st.warning(f"⚠️ {check_count}人に確認事項があります。表の「確認事項」列を確認してください。")

    # --- ステップ4：ダウンロード ---
    st.subheader("ステップ4：給与システム取り込み用CSVをダウンロードする")
    # 取り込みに必要な列だけを選んで出力します
    export_columns = ["従業員名", "基本給", "通勤手当", "残業時間", "残業代", "欠勤控除", "総支給額"]
    show_download_button(result[export_columns], "payroll-import.csv", "payroll")


# =============================================================================
# 機能2：経理仕訳の自動推論
# =============================================================================


def prepare_rules(rules_table):
    """画面で編集されたルール表から、未入力の行を除いて使いやすい形に整えます。"""
    rules = []
    for rule in rules_table.to_dict("records"):
        keyword = rule.get("キーワード")
        direction = rule.get("入出金区分")
        account = rule.get("勘定科目")

        # 空欄のキーワードはすべての取引に当てはまってしまうため、必ず除外します
        if pd.isna(keyword) or pd.isna(direction) or pd.isna(account):
            continue
        if normalize_text(keyword) == "" or str(account).strip() == "":
            continue

        rules.append(
            {
                "キーワード": normalize_text(keyword),
                "入出金区分": direction,
                "勘定科目": str(account).strip(),
            }
        )
    return rules


def infer_account(description, direction, rules):
    """摘要の文章から勘定科目を推論します。当てはまったルールのキーワードも一緒に返します。"""
    normalized_description = normalize_text(description)

    # ルールを上から順番に調べて、最初に当てはまったものを採用します
    for rule in rules:
        direction_matches = rule["入出金区分"] in (direction, "両方")
        if direction_matches and rule["キーワード"] in normalized_description:
            return rule["勘定科目"], rule["キーワード"]

    # どのルールにも当てはまらなければ、仮の科目を付けて「要確認」にします
    if direction == "入金":
        return UNMATCHED_DEPOSIT_ACCOUNT, None
    return UNMATCHED_WITHDRAWAL_ACCOUNT, None


def validate_bank_row(row_number, row, parsed_date, amount):
    """銀行明細の1行に、仕訳を作れない値がないかを調べます。"""
    errors = []
    if pd.isna(parsed_date):
        errors.append(f"{row_number}行目：日付「{row['日付']}」を読み取れません")
    if row["入出金区分"] not in ("入金", "出金"):
        errors.append(f"{row_number}行目：入出金区分「{row['入出金区分']}」は「入金」か「出金」にしてください")
    if pd.isna(amount) or amount <= 0 or amount != int(amount):
        errors.append(f"{row_number}行目：金額「{row['金額']}」は1円以上の整数にしてください")
    return errors


def create_journal_entries(table, rules):
    """銀行明細を1行ずつ仕訳データに変換します。問題のある行はエラーとして返します。"""
    entries = []
    errors = []
    amounts = to_number(table["金額"])

    # ここで取引を1行ずつ順番に仕訳へ変換しています
    for row_number, (index, row) in enumerate(table.iterrows(), start=1):
        # 銀行ごとに違う日付の書き方を読み取ります（読めなければ空になります）
        parsed_date = pd.to_datetime(normalize_text(row["日付"]), errors="coerce")
        amount = amounts.loc[index]

        row_errors = validate_bank_row(row_number, row, parsed_date, amount)
        if row_errors:
            errors.extend(row_errors)
            continue

        amount = int(amount)
        account, keyword = infer_account(row["摘要"], row["入出金区分"], rules)

        # 入金：預金が増える → 借方に普通預金、貸方に推論した科目
        # 出金：預金が減る　 → 借方に推論した科目、貸方に普通預金
        if row["入出金区分"] == "入金":
            debit_account, credit_account = BANK_ACCOUNT_NAME, account
        else:
            debit_account, credit_account = account, BANK_ACCOUNT_NAME

        entries.append(
            {
                "日付": parsed_date.strftime("%Y/%m/%d"),
                "借方勘定科目": debit_account,
                "借方金額": amount,
                "貸方勘定科目": credit_account,
                "貸方金額": amount,
                "摘要": row["摘要"],
                "判定": "自動" if keyword else "要確認",
                "根拠キーワード": keyword if keyword else "",
            }
        )

    return pd.DataFrame(entries), errors


def highlight_needs_review(row):
    """「要確認」の行に色を付けて目立たせます。"""
    if row["判定"] == "要確認":
        return ["background-color: #fff3cd; color: #664d03"] * len(row)
    return [""] * len(row)


def show_journal_page():
    """機能2の画面を表示します。"""
    st.header("📒 経理仕訳の自動推論")
    st.write("銀行明細のCSVをアップロードすると、摘要のキーワードから勘定科目を推論して仕訳を作ります。")

    # --- ステップ1：CSVの読み込み ---
    st.subheader("ステップ1：銀行明細を読み込む")
    st.caption("必要な列：" + "、".join(BANK_REQUIRED_COLUMNS))
    table = load_input_csv("銀行明細CSVをアップロード", SAMPLE_BANK_PATH, "journal")

    if table is None:
        return

    missing_columns = find_missing_columns(table, BANK_REQUIRED_COLUMNS)
    if missing_columns:
        st.error("CSVに次の列が見つかりません：" + "、".join(missing_columns))
        return

    # --- ステップ2：推論ルールの確認・編集 ---
    st.subheader("ステップ2：推論ルールを確認する")
    with st.expander("キーワードと勘定科目のルール表を見る・編集する"):
        st.caption(
            "上の行から順に調べ、最初に当てはまったルールを使います。"
            "表の一番下で行を追加でき、編集すると結果がすぐ更新されます。"
            "全角・半角、大文字・小文字の違いは気にしなくて大丈夫です。"
        )
        # ここでルール表を画面に表示し、その場で編集できるようにしています
        edited_rules = st.data_editor(
            pd.DataFrame(DEFAULT_RULES),
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "入出金区分": st.column_config.SelectboxColumn(
                    "入出金区分", options=["入金", "出金", "両方"], required=True
                ),
            },
            key="journal_rules",
        )

    # --- ステップ3：仕訳の作成と結果の表示 ---
    st.subheader("ステップ3：仕訳の結果を確認する")
    rules = prepare_rules(edited_rules)
    entries, errors = create_journal_entries(table, rules)

    # 問題のある行があるまま仕訳を出力しないよう、ここで止めます
    if errors:
        show_error_list("データに修正が必要な箇所があります", errors)
        return

    review_count = int((entries["判定"] == "要確認").sum())
    automatic_count = len(entries) - review_count

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("取引件数", f"{len(entries)} 件")
    metric_2.metric("自動で推論", f"{automatic_count} 件")
    metric_3.metric("要確認", f"{review_count} 件")

    show_time_saving(len(entries), MANUAL_MINUTES_PER_TRANSACTION, "件")

    # ここで仕訳の表を画面に表示しています（要確認の行は黄色になります）
    st.dataframe(entries.style.apply(highlight_needs_review, axis=1), hide_index=True)

    if review_count > 0:
        st.warning(
            f"⚠️ 黄色の{review_count}件はキーワードに当てはまらず、"
            f"仮の科目（{UNMATCHED_DEPOSIT_ACCOUNT}・{UNMATCHED_WITHDRAWAL_ACCOUNT}）にしています。"
            "ステップ2でルールを追加すると自動で分類できます。"
        )
    st.caption("※推論はキーワードによる機械的な判定です。会計ソフトへ取り込む前に内容をご確認ください。")

    # --- ステップ4：ダウンロード ---
    st.subheader("ステップ4：会計ソフト取り込み用CSVをダウンロードする")
    # 取り込みに不要な「判定」「根拠キーワード」は除いて出力します
    export_columns = ["日付", "借方勘定科目", "借方金額", "貸方勘定科目", "貸方金額", "摘要"]
    show_download_button(entries[export_columns], "journal-import.csv", "journal")


# =============================================================================
# アプリ全体の組み立て（ここからプログラムが動き始めます）
# =============================================================================


def main():
    """画面全体の設定をして、サイドバーで選ばれた機能を表示します。"""
    st.set_page_config(page_title="バックオフィス業務自動化デモ", page_icon="🏢", layout="wide")

    # サイドバーに機能の切り替えメニューを表示します
    st.sidebar.title("🏢 バックオフィス業務自動化デモ")
    selected_page = st.sidebar.radio(
        "使いたい機能を選んでください",
        ["💰 給与計算の自動化", "📒 経理仕訳の自動推論"],
    )
    st.sidebar.divider()
    st.sidebar.caption(
        "これはデモアプリです。税金・社会保険料の控除や消費税の区分は扱いません。"
        "アップロードしたデータはこのアプリの処理にのみ使い、ファイルとして保存しません。"
    )

    # 選ばれた機能の画面を表示します
    if selected_page == "💰 給与計算の自動化":
        show_payroll_page()
    else:
        show_journal_page()


# このファイルが実行されたら、main の処理を呼び出します
main()
