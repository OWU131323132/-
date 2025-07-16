import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import re

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

# AIに細かく指示
def analyze_nutrition_with_rda(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"料理名「{dish_name}」の主な食材と、以下の栄養素を表形式で出してください：\n"
        "エネルギー(kcal)、たんぱく質(g)、脂質(g)、糖質(g)、カリウム(mg)、カルシウム(mg)、鉄(mg)、ビタミン総量(mg)、食物繊維(g)、塩分(g)。\n"
        "さらに、日本の成人男性（30歳〜49歳）の1日推奨摂取量も同じ栄養素で教えてください。\n"
        "【例】\n"
        "| 食材 | エネルギー(kcal) | たんぱく質(g) | 脂質(g) | 糖質(g) | カリウム(mg) | カルシウム(mg) | 鉄(mg) | ビタミン総量(mg) | 食物繊維(g) | 塩分(g) |\n"
        "| 鶏肉 | 150 | 20 | 10 | 0 | 300 | 20 | 1.0 | 0.5 | 0 | 0.5 |\n"
        "\n"
        "【1日推奨量】\n"
        "| 栄養素 | 推奨量 |\n"
        "| エネルギー | 2600 kcal |\n"
        "| たんぱく質 | 65 g |\n"
        "| 脂質 | 70 g |\n"
        "| 糖質 | 330 g |\n"
        "| カリウム | 2500 mg |\n"
        "| カルシウム | 750 mg |\n"
        "| 鉄 | 7.5 mg |\n"
        "| ビタミン総量 | 100 mg |\n"
        "| 食物繊維 | 21 g |\n"
        "| 塩分 | 7.5 g |"
    )
    response = model.generate_content(prompt)
    return response.text

def parse_tables(text):
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    food_data, rda_data = [], []
    rda_mode = False

    for line in lines:
        if "【1日推奨量】" in line:
            rda_mode = True
            continue
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) < 2:
            continue
        if rda_mode:
            if len(cols) == 2:
                rda_data.append(cols)
        else:
            if len(cols) >= 11 and cols[0] != "食材":
                food_data.append(cols)

    food_columns = ['食材', 'エネルギー(kcal)', 'たんぱく質(g)', '脂質(g)', '糖質(g)',
                    'カリウム(mg)', 'カルシウム(mg)', '鉄(mg)', 'ビタミン総量(mg)', '食物繊維(g)', '塩分(g)']
    df_food = pd.DataFrame(food_data, columns=food_columns)

    for col in food_columns[1:]:
        df_food[col] = pd.to_numeric(df_food[col], errors='coerce').fillna(0)

    df_rda = pd.DataFrame(rda_data, columns=['栄養素', '推奨量'])
    df_rda['推奨量'] = df_rda['推奨量'].str.replace('kcal', '').str.replace('g', '').str.replace('mg', '').astype(float)

    return df_food, df_rda

def sum_nutrients(df):
    total = df.drop(columns=['食材']).sum().reset_index()
    total.columns = ['栄養素', '摂取量']
    return total

def plot_comparison_chart(total, rda_df):
    merged = pd.merge(total, rda_df, left_on='栄養素', right_on='栄養素', how='left')
    merged = merged.dropna()
    merged['摂取率(%)'] = (merged['摂取量'] / merged['推奨量']) * 100

    st.subheader("✅ 摂取量 vs 推奨量")
    st.dataframe(merged[['栄養素', '摂取量', '推奨量', '摂取率(%)']])

    fig = px.bar(merged, x='栄養素', y='摂取率(%)', title="推奨量達成率（%）", range_y=[0, 150], color='摂取率(%)', color_continuous_scale='Blues')
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.set_page_config(page_title="AI栄養解析 RDA対応版", layout="wide")
    st.title("🍽️ AI栄養解析＆1日推奨摂取量比較")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください")
        return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []

    dish = st.text_input("料理名を入力（例：親子丼）")
    if st.button("AI解析実行"):
        if dish.strip():
            with st.spinner("AI解析中..."):
                result = analyze_nutrition_with_rda(dish, api_key)
                df_food, df_rda = parse_tables(result)
                st.session_state.last_df_food = df_food
                st.session_state.last_df_rda = df_rda
                st.success("解析完了！")
                st.text(result)

    if "last_df_food" in st.session_state:
        st.subheader("解析結果（料理の栄養素）")
        st.dataframe(st.session_state.last_df_food)

        total = sum_nutrients(st.session_state.last_df_food)
        st.subheader("料理の栄養素 合計")
        st.dataframe(total)

        st.subheader("1日推奨量 (RDA)")
        st.dataframe(st.session_state.last_df_rda)

        plot_comparison_chart(total, st.session_state.last_df_rda)

        if st.button("食事履歴に追加"):
            row = total.set_index('栄養素')['摂取量'].to_dict()
            row['料理名'] = dish
            st.session_state.meal_log.append(row)
            st.success("追加しました")

    st.header("🍽️ 食事履歴")
    if st.session_state.meal_log:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)
    else:
        st.info("まだ履歴がありません")

if __name__ == "__main__":
    main()
