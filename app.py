import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import re

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

def analyze_nutrition_by_text(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"料理名「{dish_name}」の主な食材と、"
        "カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)、食物繊維(g)、"
        "カルシウム(mg)、鉄(mg)、ビタミンC(mg)を含む栄養素を表形式で教えてください。\n"
        "例:\n"
        "| 食材          | カロリー(kcal) | タンパク質(g) | 脂質(g) | 炭水化物(g) | 食物繊維(g) | カルシウム(mg) | 鉄(mg) | ビタミンC(mg) |\n"
        "|---------------|----------------|---------------|---------|-------------|-------------|----------------|---------|---------------|\n"
        "| 鶏むね肉(100g) | 100            | 20            | 1       | 0           | 0           | 15             | 1       | 0             |"
    )
    response = model.generate_content(prompt)
    return response.text

def parse_nutrition_text(text):
    lines = text.strip().splitlines()
    data = []
    header = []
    for line in lines:
        if line.strip() == '':
            continue
        # 罫線行や不要行を除外
        if re.match(r"^\s*\|?-+\|?-+\|?-+\|?-+\|?-+\|?-+\|?-+\|?-+\|?-+\|?$", line):
            continue
        if line.startswith('|'):
            cols = [c.strip() for c in line.strip('|').split('|')]
            # ヘッダー行の認識（1行目）
            if not header:
                header = cols
                continue
            # 合計行や目安、強調マークのある行はスキップ
            if any(x in cols[0] for x in ['合計', '目安', '**', '—', '合', '計']):
                continue

            # 数字以外や約を除去してfloat化、失敗したら0に
            row = {}
            for i, val in enumerate(cols):
                colname = header[i]
                if i == 0:
                    # 食材名はそのまま
                    row[colname] = val
                else:
                    # 数字部分のみ抽出
                    val_clean = val.replace('約', '').replace('g', '').replace('mg', '').replace('kcal', '').replace('**', '').replace(',', '').strip()
                    match = re.search(r'[\d\.]+', val_clean)
                    if match:
                        try:
                            row[colname] = float(match.group())
                        except:
                            row[colname] = 0.0
                    else:
                        row[colname] = 0.0
            data.append(row)
    return pd.DataFrame(data)

def sum_nutrition(log_df):
    if log_df.empty:
        return None
    # 食材列を除いて合計
    return log_df.drop(columns=[log_df.columns[0]]).sum()

def plot_nutrition_bar(nutrition_sum, goal_nutrition):
    categories = list(goal_nutrition.keys())
    values = [nutrition_sum.get(cat, 0) for cat in categories]
    goals = [goal_nutrition.get(cat, 1) for cat in categories]  # 0防止で1に

    percentages = [v/g*100 if g > 0 else 0 for v, g in zip(values, goals)]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=categories,
        x=percentages,
        orientation='h',
        text=[f"{values[i]:.1f} / {goals[i]}" for i in range(len(categories))],
        textposition='outside',
        marker_color='seagreen',
        name='達成度 (%)'
    ))

    fig.update_layout(
        title='今日の栄養摂取の目標達成度（%）',
        xaxis=dict(title='達成率 (%)', range=[0, max(110, max(percentages)*1.1)]),
        yaxis=dict(title='栄養素'),
        bargap=0.3,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.set_page_config(page_title="AI栄養解析＆献立提案", layout="wide")
    st.title("🍽️ AI栄養解析＆献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーをSecretsに設定するか入力してください。")
        return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = pd.DataFrame()

    st.header("1. 料理名入力で栄養解析（写真は任意）")
    dish_name = st.text_input("料理名を入力してください（例：親子丼）")
    uploaded = st.file_uploader("料理写真（任意）", type=["jpg", "jpeg", "png"])

    if st.button("栄養解析する"):
        if not dish_name.strip():
            st.warning("料理名を入力してください。")
        else:
            with st.spinner("AI解析中…"):
                try:
                    text_result = analyze_nutrition_by_text(dish_name, api_key)
                    with st.expander("解析用テキスト（Markdown表形式）"):
                        st.code(text_result)

                    df = parse_nutrition_text(text_result)
                    if not df.empty:
                        st.subheader("解析結果（表形式）")
                        st.dataframe(df.style.format("{:.1f}"))
                        if st.button("この料理を食事履歴に追加"):
                            # セッションステートのDataFrameに結合して重複防止（行のID等が無いので単純結合）
                            if st.session_state.meal_log.empty:
                                st.session_state.meal_log = df
                            else:
                                st.session_state.meal_log = pd.concat([st.session_state.meal_log, df], ignore_index=True)
                            st.success("食事履歴に追加しました！")
                    else:
                        st.warning("解析結果の形式が不正確です。")
                except Exception as e:
                    st.error(f"解析に失敗しました: {e}")

    st.header("2. 食事履歴")
    if st.session_state.meal_log.empty:
        st.info("まだ食事履歴はありません。栄養解析した料理を追加してください。")
    else:
        df_log = st.session_state.meal_log.copy()
        # 不要な行や無効データが入っていたら削除（食材名が空やnullなら除外）
        df_log = df_log[df_log[df_log.columns[0]].astype(str).str.strip() != '']
        st.dataframe(df_log.style.format("{:.1f}"))

        nutrition_sum = sum_nutrition(df_log)
        if nutrition_sum is not None:
            st.write("### 今日の摂取合計")
            for k, v in nutrition_sum.items():
                st.write(f"{k}: {v:.1f}")

    st.header("3. 目標設定＆AI献立提案")
    goal = st.selectbox("今日の目標を選択してください", [
        "筋肉を増やしたい",
        "体重を減らしたい",
        "健康的な食生活を維持したい",
        "バランスの良い食事を取りたい"
    ])

    # 目標に応じた理想栄養素（例、男女差は考慮せずざっくり）
    goal_dict = {
        "筋肉を増やしたい": {
            'カロリー(kcal)': 2500,
            'タンパク質(g)': 150,
            '脂質(g)': 70,
            '炭水化物(g)': 300,
            '食物繊維(g)': 25,
            'カルシウム(mg)': 800,
            '鉄(mg)': 10,
            'ビタミンC(mg)': 100
        },
        "体重を減らしたい": {
            'カロリー(kcal)': 1800,
            'タンパク質(g)': 100,
            '脂質(g)': 50,
            '炭水化物(g)': 150,
            '食物繊維(g)': 20,
            'カルシウム(mg)': 700,
            '鉄(mg)': 8,
            'ビタミンC(mg)': 80
        },
        "健康的な食生活を維持したい": {
            'カロリー(kcal)': 2000,
            'タンパク質(g)': 120,
            '脂質(g)': 60,
            '炭水化物(g)': 220,
            '食物繊維(g)': 22,
            'カルシウム(mg)': 750,
            '鉄(mg)': 9,
            'ビタミンC(mg)': 90
        },
        "バランスの良い食事を取りたい": {
            'カロリー(kcal)': 2200,
            'タンパク質(g)': 130,
            '脂質(g)': 65,
            '炭水化物(g)': 250,
            '食物繊維(g)': 23,
            'カルシウム(mg)': 780,
            '鉄(mg)': 9.5,
            'ビタミンC(mg)': 95
        }
    }

    if st.button("栄養達成度を表示"):
        if st.session_state.meal_log.empty:
            st.warning("まず食事履歴を追加してください。")
        else:
            plot_nutrition_bar(sum_nutrition(st.session_state.meal_log), goal_dict[goal])

    if st.button("AIに献立提案を依頼"):
        if st.session_state.meal_log.empty:
            st.warning("まず食事履歴を追加してください。")
        else:
            with st.spinner("献立提案を生成中…"):
                try:
                    nutrition_sum = sum_nutrition(st.session_state.meal_log)
                    prompt = (
                        f"あなたの今日の食事履歴の栄養摂取合計は以下の通りです。\n"
                        f"{nutrition_sum.to_dict()}\n"
                        f"目標は「{goal}」です。これを達成するために、残りの食事で摂るべき献立を提案してください。"
                    )
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    st.subheader("🤖 AIの献立提案")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"献立提案の生成に失敗しました: {e}")

if __name__ == "__main__":
    main()
