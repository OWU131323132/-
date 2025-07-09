import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai

# APIキー取得・設定
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)

st.title("料理写真から栄養バランス解析＆AI献立提案")

# 写真アップロード
uploaded_file = st.file_uploader("料理写真をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    st.image(uploaded_file, caption="アップロードされた写真", use_column_width=True)

    # --- ここで画像解析APIを呼び出して食材を特定すると想定 ---
    # 食材例（仮）
    recognized_ingredients = ["鶏肉", "野菜", "ご飯"]

    st.write("認識された食材:", recognized_ingredients)

    # 栄養データ読み込み
    nutrition_df = pd.read_csv("data/nutrition_data.csv")

    # 食材に対応する栄養素を抽出
    filtered_df = nutrition_df[nutrition_df['food'].isin(recognized_ingredients)]

    st.write("栄養情報")
    st.dataframe(filtered_df)

    # 栄養素のグラフ表示例
    fig = px.bar(filtered_df, x='food', y=['calories', 'protein', 'fat', 'carbs'], 
                 title="栄養バランス")
    st.plotly_chart(fig)

    # AIに献立提案を質問
    prompt = f"次の食材を使って健康的な献立を提案してください：{', '.join(recognized_ingredients)}"
    model = genai.Model("gemini-2.0-flash-lite")
    response = model.generate_content(prompt)

    st.subheader("AIによる献立提案")
    st.write(response.text)
