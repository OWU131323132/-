import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import re

# --- 一日の目安栄養素 ---
DAILY_REQUIREMENT = {
    'エネルギー(kcal)': 2500,
    'たんぱく質(g)': 65,
    '脂質(g)': 70,
    '糖質(g)': 330,
    'カリウム(mg)': 2500,
    'カルシウム(mg)': 800,
    '鉄(mg)': 7.0,
    'ビタミンC(mg)': 100,
    '食物繊維(g)': 21,
    '食塩相当量(g)': 7.5
}

# --- APIキー取得 ---
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキー:", type="password")

# --- 栄養解析 ---
def analyze_nutrition_by_text(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"料理名「{dish_name}」の主な食材と、"
        "エネルギー(kcal)、たんぱく質(g)、脂質(g)、糖質(g)、カリウム(mg)、"
        "カルシウム(mg)、鉄(mg)、ビタミンC(mg)、食物繊維(g)、食塩相当量(g) "
        "を表形式で教えてください。\n"
        "例:\n"
        "| 食材 | エネルギー(kcal) | たんぱく質(g) | 脂質(g) | 糖質(g) | カリウム(mg) | カルシウム(mg) | 鉄(mg) | ビタミンC(mg) | 食物繊維(g) | 食塩相当量(g) |"
    )
    return model.generate_content(prompt).text

# --- DataFrame化 ---
def parse_nutrition_text(text):
    lines = text.strip().splitlines()
    data = []
    for line in lines:
        if '|' not in line: continue
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) < 11: continue
        name = cols[0]
        def clean(val):
            val = re.sub(r"[^\d\.]", "", val)
            return float(val) if val else 0.0
        try:
            values = [clean(x) for x in cols[1:11]]
            data.append({
                '食材': name,
                'エネルギー(kcal)': values[0],
                'たんぱく質(g)': values[1],
                '脂質(g)': values[2],
                '糖質(g)': values[3],
                'カリウム(mg)': values[4],
                'カルシウム(mg)': values[5],
                '鉄(mg)': values[6],
                'ビタミンC(mg)': values[7],
                '食物繊維(g)': values[8],
                '食塩相当量(g)': values[9],
            })
        except:
            continue
    return pd.DataFrame(data)

# --- 合計表示 ---
def display_totals(df):
    total = df.drop(columns=['食材']).sum()
    st.write("#### この料理の栄養合計")
    for k, v in total.items():
        st.write(f"{k}: {v:.1f}")
    return total

# --- 一日目安と比較 ---
def compare_to_daily(total_sum):
    st.write("#### 一日摂取目安量との比較")
    for key, target in DAILY_REQUIREMENT.items():
        actual = total_sum.get(key, 0)
        percent = (actual / target) * 100 if target > 0 else 0
        st.write(f"{key}: {actual:.1f} / {target} （{percent:.1f}%）")

# --- 合計栄養計算 ---
def sum_nutrition(log):
    if not log: return None
    df = pd.DataFrame(log)
    return df.drop(columns=['料理名']).sum()

# --- AI献立 ---
def generate_meal_plan(api_key, goal, total_sum):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        "私は今日以下の栄養を摂取しました：\n" +
        "\n".join([f"{k}: {v:.1f}" for k, v in total_sum.items()]) +
        f"\n目標は「{goal}」。この目標に合う残りの食事提案をお願いします。"
    )
    return model.generate_content(prompt).text

# --- メイン ---
def main():
    st.set_page_config(page_title="AI栄養解析・献立", layout="wide")
    st.title("🥗 AI栄養解析＆一日目安付き献立提案")

    api_key = get_api_key()
    if not api_key: return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []
    if "current_df" not in st.session_state:
        st.session_state.current_df, st.session_state.current_dish = None, ""

    dish_name = st.text_input("料理名を入力")
    if st.button("解析する"):
        st.session_state.current_dish = dish_name
        text = analyze_nutrition_by_text(dish_name, api_key)
        df = parse_nutrition_text(text)
        if df.empty:
            st.warning("解析失敗")
        else:
            st.session_state.current_df = df
            st.success("解析完了！")
            st.text(text)

    if st.session_state.current_df is not None:
        st.subheader("解析結果")
        st.dataframe(st.session_state.current_df)

        total = display_totals(st.session_state.current_df)
        compare_to_daily(total)

        if st.button("食事履歴に追加"):
            meal = total.to_dict()
            meal['料理名'] = st.session_state.current_dish
            st.session_state.meal_log.append(meal)
            st.success("追加しました！")

            # 解析結果リセット
            st.session_state.current_df = None
            st.session_state.current_dish = ""

    st.header("🍴 食事履歴")
    if st.session_state.meal_log:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)
        sum_today = sum_nutrition(st.session_state.meal_log)
        st.write("### 今日の累計")
        for k, v in sum_today.items():
            if k != '料理名':
                st.write(f"{k}: {v:.1f} / {DAILY_REQUIREMENT.get(k, '不明')}")

        compare_to_daily(sum_today)
    else:
        st.info("まだ食事履歴はありません")

    st.header("🎯 目標設定＆献立提案")
    goal = st.selectbox("目標選択", ["筋肉を増やしたい", "体重を減らしたい", "バランスの良い食事"])
    if st.button("AI献立提案"):
        sum_today = sum_nutrition(st.session_state.meal_log) or pd.Series({k: 0.0 for k in DAILY_REQUIREMENT})
        with st.spinner("提案生成中…"):
            response = generate_meal_plan(api_key, goal, sum_today)
            st.subheader("🤖 AIの献立提案")
            st.write(response)

if __name__ == "__main__":
    main()
