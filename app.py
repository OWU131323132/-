import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
import re

# --- APIキー取得 ---
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

# --- 栄養解析 ---
def analyze_nutrition_by_text(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"料理名「{dish_name}」の主な食材と、"
        "カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)を表形式で教えてください。\n"
        "例:\n"
        "| 食材 | カロリー(kcal) | タンパク質(g) | 脂質(g) | 炭水化物(g) |\n"
        "|---------------|----------------|---------------|---------|-------------|\n"
        "| りんご | 52 | 0.3 | 0.2 | 14 |\n"
        "| バナナ | 89 | 1.1 | 0.3 | 23 |"
    )
    response = model.generate_content(prompt)
    return response.text

# --- 解析結果からDataFrame ---
def parse_nutrition_text(text):
    lines = text.strip().splitlines()
    data = []
    for line in lines:
        if '|' not in line:
            continue
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) < 5:
            continue
        if any(x in cols[0] for x in ['合計', '目安', '**', '—', '合', '計']):
            continue
        name = cols[0]

        def clean_value(val):
            val = val.replace('約', '').replace('g', '').replace('kcal', '')\
                     .replace('**', '').replace(',', '').strip()
            m = re.search(r'[\d\.]+', val)
            return float(m.group()) if m else 0.0

        try:
            calories = clean_value(cols[1])
            protein = clean_value(cols[2])
            fat = clean_value(cols[3])
            carb = clean_value(cols[4])
        except:
            continue

        data.append({
            '食材': name,
            'カロリー(kcal)': calories,
            'タンパク質(g)': protein,
            '脂質(g)': fat,
            '炭水化物(g)': carb
        })

    return pd.DataFrame(data)

# --- 円グラフ ---
def plot_macro_pie(df):
    if df.empty:
        st.info("解析結果が空です。")
        return
    total = df[['タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum().reset_index()
    total.columns = ['栄養素', '量(g)']
    fig = px.pie(total, names='栄養素', values='量(g)', title='マクロ栄養素割合')
    st.plotly_chart(fig, use_container_width=True)

# --- 栄養素合計 ---
def sum_nutrition(log):
    if not log:
        return None
    df = pd.DataFrame(log)
    return df[['カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum()

# --- 献立提案 ---
def generate_meal_plan(api_key, goal, nutrition_summary):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"私は今日これまでに以下の栄養素を摂取しました：\n"
        f"カロリー: {nutrition_summary['カロリー(kcal)']:.1f} kcal、"
        f"タンパク質: {nutrition_summary['タンパク質(g)']:.1f} g、"
        f"脂質: {nutrition_summary['脂質(g)']:.1f} g、"
        f"炭水化物: {nutrition_summary['炭水化物(g)']:.1f} g。\n"
        f"目標は「{goal}」です。"
        "この目標に合う今日の残りの食事のおすすめ献立を提案してください。"
    )
    return model.generate_content(prompt).text

# --- メイン ---
def main():
    st.set_page_config(page_title="AI栄養解析＆献立提案", layout="wide")
    st.title("🍽️ AI栄養解析＆献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    # セッション状態初期化
    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []
    if "current_df" not in st.session_state:
        st.session_state.current_df = None
        st.session_state.current_dish = ""

    # 栄養解析
    st.header("1. 料理名入力で栄養解析")
    dish_name = st.text_input("料理名を入力（例：親子丼）")

    if st.button("栄養解析する"):
        if not dish_name.strip():
            st.warning("料理名を入力してください。")
        else:
            with st.spinner("AI解析中…"):
                text_result = analyze_nutrition_by_text(dish_name, api_key)
                df = parse_nutrition_text(text_result)
                if df.empty:
                    st.warning("解析に失敗しました。")
                else:
                    st.session_state.current_df = df
                    st.session_state.current_dish = dish_name
                    st.success("解析完了！")
                    st.text(text_result)

    if st.session_state.current_df is not None:
        st.subheader("解析結果（表形式）")
        st.dataframe(st.session_state.current_df)
        plot_macro_pie(st.session_state.current_df)

        if st.button("この料理を食事履歴に追加"):
            total = st.session_state.current_df[['カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum()
            st.session_state.meal_log.append({
                '料理名': st.session_state.current_dish,
                'カロリー(kcal)': total['カロリー(kcal)'],
                'タンパク質(g)': total['タンパク質(g)'],
                '脂質(g)': total['脂質(g)'],
                '炭水化物(g)': total['炭水化物(g)']
            })
            st.success("食事履歴に追加しました！")

    # 食事履歴
    st.header("2. 食事履歴")
    if not st.session_state.meal_log:
        st.info("まだ食事履歴はありません。")
    else:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)

        nutrition_sum = sum_nutrition(st.session_state.meal_log)
        st.write("### 今日の摂取合計")
        st.write(f"カロリー: {nutrition_sum['カロリー(kcal)']:.1f} kcal")
        st.write(f"タンパク質: {nutrition_sum['タンパク質(g)']:.1f} g")
        st.write(f"脂質: {nutrition_sum['脂質(g)']:.1f} g")
        st.write(f"炭水化物: {nutrition_sum['炭水化物(g)']:.1f} g")

    # 献立提案
    st.header("3. 目標設定＆AI献立提案")
    goal = st.selectbox("目標を選択", ["筋肉を増やしたい", "体重を減らしたい", "健康的な食生活を維持したい", "バランスの良い食事を取りたい"])

    if st.button("AIに献立提案を依頼"):
        nutrition_sum = sum_nutrition(st.session_state.meal_log)
        if nutrition_sum is None:
            nutrition_sum = {'カロリー(kcal)': 0, 'タンパク質(g)': 0, '脂質(g)': 0, '炭水化物(g)': 0}
        with st.spinner("献立提案中…"):
            result = generate_meal_plan(api_key, goal, nutrition_sum)
            st.subheader("🤖 AIの献立提案")
            st.write(result)

if __name__ == "__main__":
    main()
