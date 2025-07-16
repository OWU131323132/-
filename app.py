import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px

# --- APIキーの取得 ---
import streamlit as st
import google.generativeai as genai

api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
st.title("学習アシスタントアプリ")


# --- 画像をGeminiに解析させる ---
def analyze_image_with_gemini(image_file, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')  # または 'gemini-1.0-pro' など
    image_bytes = image_file.getvalue()
    image_data = {"mime_type": image_file.type, "data": image_bytes}

    prompt = (
        "この料理画像に含まれる食材を特定し、次の形式で栄養情報を出力してください：\n\n"
        "食材：カロリー (kcal), タンパク質 (g), 脂質 (g), 炭水化物 (g)\n\n"
        "例：\n"
        "りんご：52 kcal, 0.3 g, 0.2 g, 14 g\n"
        "バナナ：89 kcal, 1.1 g, 0.3 g, 23 g"
    )

    response = model.generate_content([prompt, image_data])
    return response.text

# --- AI出力のテキストをDataFrameに変換 ---
def parse_nutrition_text_to_df(text):
    lines = [line for line in text.splitlines() if "：" in line and "kcal" in line]
    data = []
    for line in lines:
        try:
            name, rest = line.split("：")
            parts = rest.replace("kcal", "").replace("g", "").replace(" ", "").split(",")
            if len(parts) == 4:
                cal, protein, fat, carbs = map(float, parts)
                data.append({
                    "食材": name,
                    "カロリー": cal,
                    "タンパク質": protein,
                    "脂質": fat,
                    "炭水化物": carbs
                })
        except:
            continue
    return pd.DataFrame(data)

# --- 栄養バランスを円グラフで表示 ---
def show_macro_chart(df):
    if df.empty:
        return
    total = df[["タンパク質", "脂質", "炭水化物"]].sum().reset_index()
    total.columns = ["栄養素", "量 (g)"]
    fig = px.pie(total, names="栄養素", values="量 (g)", title="マクロ栄養バランス")
    st.plotly_chart(fig, use_container_width=True)

# --- メイン処理 ---
def main():
    st.title("🍱 AI栄養解析 & 献立提案アプリ")

    api_key = st.secrets.get("GEMINI_API_KEY")  # get()で安全に取得
    if not api_key:
        st.warning("APIキーを入力またはSecretsに設定してください。")
        return

    # 以下は元通り...


    # Gemini API 初期化
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"APIキーの設定に失敗しました: {e}")
        return

    # 画像アップロード
    uploaded_file = st.file_uploader("料理の画像をアップロードしてください", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file, caption="アップロード画像", use_column_width=True)
        with st.spinner("AIが画像を解析中..."):
            try:
                ai_output = analyze_image_with_gemini(uploaded_file, api_key)
                st.subheader("🔍 AIによる解析結果")
                st.text(ai_output)

                df = parse_nutrition_text_to_df(ai_output)
                if not df.empty:
                    st.subheader("📊 栄養素テーブル")
                    st.dataframe(df)
                    show_macro_chart(df)
                else:
                    st.warning("解析結果を正しく読み取れませんでした。フォーマットが不明瞭な可能性があります。")

            except Exception as e:
                st.error(f"画像解析中にエラーが発生しました: {e}")

    # ユーザーの質問・献立提案
    st.markdown("---")
    st.subheader("💬 AIに質問・献立提案を依頼")
    user_input = st.text_area("質問を入力してください（例：高タンパクな朝食メニューは？）")
    if st.button("AIに質問する") and user_input.strip():
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(user_input)
            st.markdown("### 🤖 AIの回答")
            st.write(response.text)
        except Exception as e:
            st.error(f"AIからの回答取得に失敗しました: {e}")

if __name__ == "__main__":
    main()
