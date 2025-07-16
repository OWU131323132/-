import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px

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
        "カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)を表形式で教えてください。"
        "\n例:\nりんご：52, 0.3, 0.2, 14\nバナナ：89, 1.1, 0.3, 23"
    )
    response = model.generate_content(prompt)
    return response.text

# 以下、parse_nutrition_textやplot_macro_pieなどは前のコードと同じで使う

def main():
    st.title("🍽️ AI栄養解析＆献立提案（写真任意）")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーをSecretsに設定するか入力してください。")
        return

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []

    st.header("1. 料理名を入力して栄養解析")
    dish_name = st.text_input("料理名を入力してください（例：親子丼）")
    uploaded = st.file_uploader("料理写真（任意）", type=["jpg","jpeg","png"])

    if st.button("栄養解析する"):
        if not dish_name.strip():
            st.warning("料理名を入力してください。")
        else:
            with st.spinner("解析中…"):
                try:
                    # 画像があれば画像解析のロジックと組み合わせ可能だが、今回はテキスト解析優先
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

    # 以下は前回同様、食事履歴表示＆摂取合計、目標設定、献立提案UIを続ける
    # ...

if __name__ == "__main__":
    main()
