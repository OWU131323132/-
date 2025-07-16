import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import re

# --- APIキー取得 ---
def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    else:
        return st.text_input(
            "Gemini APIキーを入力してください:",
            type="password",
            help="Google AI StudioでAPIキーを取得してください"
        )

# --- 栄養テーブルテキストをDataFrameに変換 ---
def parse_nutrition_text(text):
    # テーブル部分のみ抽出（|区切りの行を集める）
    lines = [line.strip() for line in text.splitlines() if re.match(r'^\|.*\|$', line.strip())]

    if len(lines) < 3:
        return pd.DataFrame()  # テーブルが小さすぎるなら空返す

    # ヘッダーと区切り行は飛ばす
    header = lines[0].strip('|').split('|')
    header = [h.strip() for h in header]

    data = []
    for line in lines[2:]:  # 区切り行（2行目）以降
        row = line.strip('|').split('|')
        row = [r.strip() for r in row]
        # 「合計」などの合計行は無視する（必要なら除外）
        if any(k in row[0] for k in ['合計', '-----', '----']):
            continue
        # もし列数違うならスキップ
        if len(row) != len(header):
            continue
        data.append(row)

    df = pd.DataFrame(data, columns=header)

    # 数値カラムはfloatに変換。文字列の「約」や空白を除去してから変換
    def clean_num(x):
        if isinstance(x, str):
            x = x.replace('約', '').replace(',', '').strip()
            try:
                return float(x)
            except:
                return 0.0
        elif pd.isna(x):
            return 0.0
        return float(x)

    for col in df.columns[1:]:
        df[col] = df[col].apply(clean_num)

    return df

# --- 食事履歴の栄養素を合計 ---
def sum_nutrition(log_df):
    if log_df.empty:
        return None
    numeric_cols = log_df.columns[1:]  # 食材以外
    sums = log_df[numeric_cols].sum()
    return sums

# --- 栄養素棒グラフ（横棒） ---
def plot_nutrition_bar(nutrition_sum, goal_dict):
    if nutrition_sum is None or len(nutrition_sum) == 0:
        st.info("栄養摂取合計データがありません。")
        return

    nutrients = list(goal_dict.keys())
    goal_vals = [goal_dict[n] for n in nutrients]
    actual_vals = [nutrition_sum.get(n, 0) for n in nutrients]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=nutrients,
        x=goal_vals,
        name='目標値',
        orientation='h',
        marker=dict(color='lightgray')
    ))
    fig.add_trace(go.Bar(
        y=nutrients,
        x=actual_vals,
        name='摂取量',
        orientation='h',
        marker=dict(color='steelblue')
    ))

    fig.update_layout(
        barmode='overlay',
        title='今日の栄養摂取状況',
        xaxis_title='量',
        yaxis_title='栄養素',
        xaxis=dict(range=[0, max(max(goal_vals), max(actual_vals)) * 1.2]),
        height=400,
        margin=dict(l=120)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 1日の目標栄養素例（例：成人男性の参考値など）---
def get_daily_goal():
    return {
        "カロリー(kcal)": 2500,
        "タンパク質(g)": 60,
        "脂質(g)": 70,
        "炭水化物(g)": 310,
        "食物繊維(g)": 20,
        "カルシウム(mg)": 650,
        "鉄分(mg)": 7.5,
        "ビタミンC(mg)": 100,
        "ナトリウム(mg)": 2400,
        # 必要に応じて追加してください
    }

# --- メイン処理 ---
def main():
    st.title("料理栄養解析＆AI献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    # 食事履歴をセッションステートで管理
    if "meal_log" not in st.session_state:
        st.session_state.meal_log = pd.DataFrame()

    st.header("▼ 栄養情報の入力（任意で料理写真アップロードも可能）")
    uploaded_file = st.file_uploader("料理写真をアップロードしてください（任意）", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        from PIL import Image
        image = Image.open(uploaded_file)
        st.image(image, caption="アップロードされた画像", use_column_width=True)

    st.markdown("### 解析結果テキストをペーストしてください")
    nutrition_text = st.text_area("料理の栄養成分表（例: 食材,カロリーなどの表形式）")

    if st.button("解析して食事履歴に追加"):
        if not nutrition_text.strip():
            st.warning("解析用テキストを入力してください。")
        else:
            df = parse_nutrition_text(nutrition_text)
            if df.empty:
                st.error("解析に失敗しました。表形式のテキストを確認してください。")
            else:
                # 食事履歴に追加（既存のものがあれば結合）
                st.session_state.meal_log = pd.concat([st.session_state.meal_log, df], ignore_index=True)
                st.success("食事履歴に追加しました。")
                st.dataframe(st.session_state.meal_log)

    st.header("▼ 今日の食事履歴")
    if st.session_state.meal_log.empty:
        st.info("まだ食事履歴がありません。上のテキスト解析で追加してください。")
    else:
        st.dataframe(st.session_state.meal_log.style.format("{:.1f}", na_rep="0"))

        # 栄養合計表示
        nutrition_sum = sum_nutrition(st.session_state.meal_log)
        if nutrition_sum is not None:
            st.subheader("今日の摂取合計")
            for k, v in nutrition_sum.items():
                st.write(f"{k}: {v:.1f}")

            # 目標値取得
            goal_dict = get_daily_goal()
            plot_nutrition_bar(nutrition_sum, goal_dict)

    st.header("▼ AIに献立提案を依頼")
    user_goal = st.selectbox("あなたの目標を選択してください", ["体重維持", "筋肉増強", "ダイエット", "健康維持"])
    user_input = st.text_area("質問や献立提案を入力してください（例: 高タンパクな夕食メニューを教えて）")

    if st.button("献立提案を取得"):
        if not api_key:
            st.error("APIキーが設定されていません。")
        elif st.session_state.meal_log.empty:
            st.warning("まず食事履歴を追加してください。")
        elif not user_input.strip():
            st.warning("質問内容を入力してください。")
        else:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerateModel('gemini-2.0-flash-lite')

                nutrition_sum = sum_nutrition(st.session_state.meal_log)
                prompt = (
                    f"ユーザーの今日の食事履歴に基づく栄養摂取合計:\n{nutrition_sum.to_dict()}\n"
                    f"目標: {user_goal}\n"
                    f"この情報をもとに、残りの食事で摂るべき献立を提案してください。\n"
                    f"さらに、ユーザーの質問:\n{user_input}"
                )
                response = model.generate_content(prompt)
                st.subheader("🤖 AIの献立提案")
                st.write(response.text)
            except Exception as e:
                st.error(f"AI献立提案の生成に失敗しました: {e}")

if __name__ == "__main__":
    main()
