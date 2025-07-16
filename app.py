import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
import re

# --- APIキー取得（Secrets優先） ---
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

# --- AIにテキストで栄養解析依頼 ---
def analyze_nutrition_by_text(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"料理名「{dish_name}」の主な食材と、"
        "カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)を表形式で教えてください。"
        "\n例:\n"
        "| 食材          | カロリー(kcal) | タンパク質(g) | 脂質(g) | 炭水化物(g) |\n"
        "|---------------|----------------|---------------|---------|-------------|\n"
        "| りんご       | 52             | 0.3           | 0.2     | 14          |\n"
        "| バナナ       | 89             | 1.1           | 0.3     | 23          |"
    )
    response = model.generate_content(prompt)
    return response.text

# --- 解析テキストをきれいにDataFrame化 ---
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
            if val == '':
                return 0.0
            m = re.search(r'[\d\.]+', val)
            if m:
                return float(m.group())
            return 0.0

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

    df = pd.DataFrame(data)
    return df

# --- マクロ栄養素の円グラフ表示 ---
def plot_macro_pie(df):
    if df.empty:
        st.info("解析結果が空です。")
        return
    total = df[['タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum().reset_index()
    total.columns = ['栄養素', '量(g)']
    fig = px.pie(total, names='栄養素', values='量(g)', title='マクロ栄養素割合')
    st.plotly_chart(fig, use_container_width=True)

# --- 食事ログの栄養合計を計算 ---
def sum_nutrition(log):
    if len(log) == 0:
        return None
    df = pd.DataFrame(log)
    return df[['カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum()

# --- AIに献立提案依頼 ---
def generate_meal_plan(api_key, goal, nutrition_summary):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    if (nutrition_summary['カロリー(kcal)'] == 0 and
        nutrition_summary['タンパク質(g)'] == 0 and
        nutrition_summary['脂質(g)'] == 0 and
        nutrition_summary['炭水化物(g)'] == 0):
        prompt = (
            f"私は今日これまでにまだ何も食べていません。\n"
            f"目標は「{goal}」です。\n"
            "この目標に合うように今日の食事のおすすめ献立を提案してください。"
        )
    else:
        prompt = (
            f"私は今日これまでに以下の栄養素を摂取しました：\n"
            f"カロリー: {nutrition_summary['カロリー(kcal)']:.1f} kcal、"
            f"タンパク質: {nutrition_summary['タンパク質(g)']:.1f} g、"
            f"脂質: {nutrition_summary['脂質(g)']:.1f} g、"
            f"炭水化物: {nutrition_summary['炭水化物(g)']:.1f} g。\n"
            f"目標は「{goal}」です。\n"
            "この目標に合うように今日の残りの食事でおすすめの献立を提案してください。"
        )
    response = model.generate_content(prompt)
    return response.text

# --- メイン ---
def main():
    st.set_page_config(page_title="AI栄養解析＆献立提案", layout="wide")
    st.title("🍽️ AI栄養解析＆献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーをSecretsに設定するか入力してください。")
        return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []

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
                    st.subheader("AI解析結果（テキスト）")
                    st.text(text_result)

                    df = parse_nutrition_text(text_result)
                    if not df.empty:
                        st.subheader("解析結果（表形式）")
                        st.dataframe(df)

                        if st.button("この料理を食事履歴に追加"):
                            for _, row in df.iterrows():
                                st.session_state.meal_log.append(row.to_dict())
                            st.success("食事履歴に追加しました！")

                        plot_macro_pie(df)
                    else:
                        st.warning("解析結果の形式が不正確です。")
                except Exception as e:
                    st.error(f"解析に失敗しました: {e}")

    st.header("2. 食事履歴")
    if len(st.session_state.meal_log) == 0:
        st.info("まだ食事履歴はありません。栄養解析した料理を追加してください。")
    else:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)

        nutrition_sum = sum_nutrition(st.session_state.meal_log)
        if nutrition_sum is not None:
            st.write("### 今日の摂取合計")
            st.write(f"カロリー: {nutrition_sum['カロリー(kcal)']:.1f} kcal")
            st.write(f"タンパク質: {nutrition_sum['タンパク質(g)']:.1f} g")
            st.write(f"脂質: {nutrition_sum['脂質(g)']:.1f} g")
            st.write(f"炭水化物: {nutrition_sum['炭水化物(g)']:.1f} g")

    st.header("3. 目標設定＆AI献立提案")
    goal = st.selectbox("今日の目標を選択してください", [
        "筋肉を増やしたい",
        "体重を減らしたい",
        "健康的な食生活を維持したい",
        "バランスの良い食事を取りたい"
    ])

    if st.button("AIに献立提案を依頼"):
        with st.spinner("献立提案を生成中…"):
            try:
                if len(st.session_state.meal_log) == 0:
                    nutrition_sum = {
                        'カロリー(kcal)': 0.0,
                        'タンパク質(g)': 0.0,
                        '脂質(g)': 0.0,
                        '炭水化物(g)': 0.0
                    }
                else:
                    nutrition_sum = sum_nutrition(st.session_state.meal_log)

                response = generate_meal_plan(api_key, goal, nutrition_sum)
                st.subheader("🤖 AIの献立提案")
                st.write(response)
            except Exception as e:
                st.error(f"献立提案の生成に失敗しました: {e}")

if __name__ == "__main__":
    main()
