import streamlit as st
import google.generativeai as genai
import matplotlib.pyplot as plt
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
    for line in text.split('\n'):
        for nutrient in ["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]:
            if nutrient in line:
                try:
                    value = float(''.join(filter(str.isdigit, line)))
                    data[nutrient] = value
                except:
                    pass
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
        
        # グラフ描画
        st.subheader("摂取量のグラフ")
        nutrients = ["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]
        totals = df[nutrients].sum()

        plt.figure(figsize=(6,4))
        plt.bar(totals.index, totals.values, color="skyblue")
        plt.ylabel("合計摂取量")
        st.pyplot(plt)
    else:
        st.write("食事履歴がありません。")

# メインアプリ
def main():
    st.title("AI栄養解析＆献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
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
        totals = df[["エネルギー", "たんぱく質", "脂質", "糖質", "カリウム"]].sum()

        fig, ax = plt.subplots(figsize=(6,4))
        ax.bar(totals.index, totals.values, label="摂取量", alpha=0.7)
        ax.bar(target.keys(), target.values(), label="目標値", alpha=0.3)
        ax.legend()
        ax.set_ylabel("gまたはmg")
        st.pyplot(fig)

if __name__ == "__main__":
    main()
