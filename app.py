import streamlit as st
import google.generativeai as genai
import pandas as pd

# APIキー取得
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキー:", type="password")

# Gemini APIによる栄養解析
def analyze_nutrition(dish_name, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-pro")
    prompt = f"{dish_name}の栄養成分（エネルギー、たんぱく質、脂質、糖質、カリウム）を具体的な数値で教えてください。単位もつけてください。"
    response = model.generate_content(prompt)
    return response.text

# 栄養成分のパース
def parse_nutrition(text):
    data = {}
    import re
    for line in text.split('\n'):
        for nutrient in ["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]:
            if nutrient in line:
                match = re.search(r"([0-9]+\.?[0-9]*)", line)
                if match:
                    data[nutrient] = float(match.group(1))
    return data

# 食事履歴の保存
if "history" not in st.session_state:
    st.session_state.history = []

def add_to_history(entry):
    st.session_state.history.append(entry)

def display_history():
    if st.session_state.history:
        st.subheader("食事履歴")
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df)

        # 摂取量合計を計算
        nutrients = ["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]
        totals = df[nutrients].sum()

        st.subheader("摂取量のグラフ")
        st.bar_chart(totals)
    else:
        st.write("食事履歴がありません。")

# メインアプリ
def main():
    st.title("AI栄養解析＆献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.info("APIキーを入力してください。")
        st.stop()

    st.header("料理の栄養解析")
    dish_name = st.text_input("料理名を入力:")

    if dish_name:
        with st.spinner("AIが解析中..."):
            result = analyze_nutrition(dish_name, api_key)
            st.subheader("AI解析結果")
            st.write(result)

            nutrition_data = parse_nutrition(result)
            if nutrition_data:
                st.subheader("解析データ")
                st.write(nutrition_data)

                if st.button("食事履歴に追加"):
                    entry = {"料理名": dish_name}
                    entry.update(nutrition_data)
                    add_to_history(entry)
                    st.success("食事履歴に追加しました！")

    display_history()

    st.header("目標摂取量との比較")
    target = {"エネルギー": 2000, "たんぱく質": 100, "脂質": 60, "糖質": 250, "カリウム": 3500}
    st.write("一日目標摂取量:", target)

    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        nutrients = ["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]
        totals = df[nutrients].sum()

        df_compare = pd.DataFrame({
            "摂取量": totals,
            "目標量": pd.Series(target)
        })
        st.subheader("摂取量と目標量の比較グラフ")
        st.bar_chart(df_compare)

if __name__ == "__main__":
    main()
