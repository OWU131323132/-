import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import re

# --- APIキー ---
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

# --- AI 栄養解析 ---
def analyze_nutrition_by_text(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
料理名「{dish_name}」の食材と、下記の栄養素を表形式で教えてください：
エネルギー(kcal)、たんぱく質(g)、脂質(g)、糖質(g)、カリウム(mg)、カルシウム(mg)、鉄(mg)、ビタミンC(mg)、食物繊維(g)、塩分(g)

さらに、日本の成人男女（20〜40代）の一日推奨摂取量も同様の栄養素について教えてください。フォーマットは以下：

【解析結果】
| 食材 | エネルギー(kcal) | たんぱく質(g) | 脂質(g) | 糖質(g) | カリウム(mg) | カルシウム(mg) | 鉄(mg) | ビタミンC(mg) | 食物繊維(g) | 塩分(g) |
| ... | ... |

【1日の推奨摂取量】
| 栄養素 | 推奨量 |
| ... | ... |
"""
    response = model.generate_content(prompt)
    return response.text

# --- 解析テキストをDataFrameへ ---
def parse_nutrition_text(text):
    lines = text.strip().splitlines()
    food_data = []
    daily_data = []
    section = None

    for line in lines:
        if "【解析結果】" in line:
            section = "food"
            continue
        elif "【1日の推奨摂取量】" in line:
            section = "daily"
            continue
        if "|" not in line or "---" in line:
            continue

        cols = [c.strip() for c in line.strip('|').split('|') if c.strip()]
        if section == "food" and len(cols) == 11:
            food_data.append(cols)
        elif section == "daily" and len(cols) == 2:
            daily_data.append(cols)

    df_food = pd.DataFrame(food_data[1:], columns=food_data[0]) if food_data else pd.DataFrame()
    df_daily = pd.DataFrame(daily_data[1:], columns=daily_data[0]) if daily_data else pd.DataFrame()

    def clean_value(val):
        val = val.replace('約', '').replace('g', '').replace('mg', '').replace('kcal', '').replace(',', '').strip()
        m = re.search(r'[\d\.]+', val)
        return float(m.group()) if m else 0.0

    for col in df_food.columns[1:]:
        df_food[col] = df_food[col].apply(clean_value)
    if not df_daily.empty:
        df_daily["推奨量"] = df_daily["推奨量"].apply(clean_value)

    return df_food, df_daily

# --- 円グラフ ---
def plot_macro_pie(df):
    st.subheader("主要マクロ栄養素の割合（たんぱく質・脂質・糖質）")
    macro = df[['たんぱく質(g)', '脂質(g)', '糖質(g)']].sum().reset_index()
    macro.columns = ['栄養素', '量(g)']
    fig = px.pie(macro, names='栄養素', values='量(g)')
    st.plotly_chart(fig, use_container_width=True)

# --- 摂取合計 ---
def sum_nutrition(log):
    if not log:
        return None
    df = pd.DataFrame(log)
    return df.iloc[:, 1:].sum()

# --- メイン ---
def main():
    st.set_page_config("AI栄養解析＆推奨量比較", layout="wide")
    st.title("🍽️ AI栄養解析＆一日推奨量比較")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []
    if "current_df" not in st.session_state:
        st.session_state.current_df = None
        st.session_state.current_dish = ""
        st.session_state.daily_df = None

    st.header("1. 栄養解析")
    dish_name = st.text_input("料理名（例：親子丼）")

    if st.button("栄養解析する"):
        if not dish_name:
            st.warning("料理名を入力してください。")
        else:
            with st.spinner("AI解析中…"):
                result = analyze_nutrition_by_text(dish_name, api_key)
                df_food, df_daily = parse_nutrition_text(result)
                if df_food.empty or df_daily.empty:
                    st.error("解析失敗。もう一度試してください。")
                else:
                    st.session_state.current_df = df_food
                    st.session_state.current_dish = dish_name
                    st.session_state.daily_df = df_daily
                    st.success("解析完了！")
                    st.text(result)

    if st.session_state.current_df is not None:
        st.subheader("解析結果（表形式）")
        st.dataframe(st.session_state.current_df)

        if st.session_state.daily_df is not None:
            st.subheader("1日の推奨量")
            st.dataframe(st.session_state.daily_df)

        plot_macro_pie(st.session_state.current_df)

        if st.button("この料理を食事履歴に追加"):
            total = st.session_state.current_df.iloc[:, 1:].sum()
            entry = {'料理名': st.session_state.current_dish}
            for col, val in zip(st.session_state.current_df.columns[1:], total):
                entry[col] = val
            st.session_state.meal_log.append(entry)
            st.success("食事履歴に追加しました！")

    st.header("2. 食事履歴と合計")
    if not st.session_state.meal_log:
        st.info("まだ食事履歴はありません。")
    else:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)

        total = sum_nutrition(st.session_state.meal_log)
        st.write("### 摂取合計")
        for idx, val in zip(df_log.columns[1:], total):
            st.write(f"{idx}: {val:.1f}")

        if st.session_state.daily_df is not None:
            st.write("### 推奨量との比較")
            for idx in df_log.columns[1:]:
                daily_val = st.session_state.daily_df.loc[st.session_state.daily_df["栄養素"] == idx.replace("(g)", "").replace("(mg)", "").replace("(kcal)", ""), "推奨量"]
                if not daily_val.empty:
                    ratio = total[idx] / daily_val.values[0] * 100
                    st.write(f"{idx}: {ratio:.1f}% 達成")

if __name__ == "__main__":
    main()
