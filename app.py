import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px

def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return st.text_input("Gemini APIキーを入力してください:", type="password")

def analyze_image_with_gemini(image_file, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerateModel('gemini-2.0-flash-lite')
    img_bytes = image_file.getvalue()
    image_parts = [{"mime_type": image_file.type, "data": img_bytes}]
    prompt = (
        "以下の料理画像を見て、主な食材と概算カロリー、"
        "タンパク質・脂質・炭水化物の数値を表形式で教えてください。"
    )
    resp = model.generate_content([prompt, image_parts[0]])
    return resp.text

def parse_nutrition_text_to_df(nutrition_text):
    # 「食材：カロリー、タンパク質、脂質、炭水化物」形式のテキストを抽出して DF 化
    lines = [l for l in nutrition_text.splitlines() if ":" in l and "g" in l]
    data = []
    for line in lines:
        name, rest = line.split("：", 1)
        nums = [float(s.strip().replace("g","").replace("kcal",""))
                for s in rest.replace("kcal","").split(",")]
        if len(nums) >= 4:
            cal, prot, fat, carb = nums[:4]
            data.append({"food": name, "cal": cal, "protein": prot, "fat": fat, "carb": carb})
    return pd.DataFrame(data)

def show_macro_charts(df):
    df_sum = df[["protein","fat","carb"]].sum().reset_index()
    df_sum.columns = ["macro","value"]
    fig = px.pie(df_sum, names="macro", values="value", title="マクロ栄養素割合")
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.title("🍱 料理画像で栄養解析＆AI献立提案")
    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    uploaded = st.file_uploader("料理写真をアップロードしてください", type=["jpg","png"])
    if not uploaded:
        st.info("まず画像をアップロードしてください。")
    else:
        st.image(uploaded, use_column_width=True, caption="アップロード画像")
        with st.spinner("解析中…"):
            text = analyze_image_with_gemini(uploaded, api_key)
        st.markdown("### 📝 解析結果（AI出力）")
        st.text(text)

        df = parse_nutrition_text_to_df(text)
        if not df.empty:
            st.table(df)
            show_macro_charts(df)
        else:
            st.warning("栄養データの解析に失敗しました。フォーマットをご確認ください。")

    st.markdown("---")
    st.markdown("### 💬 AIに質問や献立提案を依頼")
    user_input = st.text_area("質問内容を入力してください")
    if st.button("質問する"):
        if user_input.strip():
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerateModel('gemini-2.0-flash-lite')
                response = model.generate_content(user_input)
                st.markdown("### AIの回答")
                st.write(response.text)
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
        else:
            st.warning("質問を入力してください。")

if __name__ == "__main__":
    main()
