import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# --- APIキーの取得 ---
def get_api_key():
    # まずSecretsから取得
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    else:
        # なければユーザー入力で取得
        return st.text_input(
            "Gemini APIキーを入力してください:",
            type="password",
            help="Google AI StudioでAPIキーを取得してください"
        )

def main():
    st.title("料理写真から栄養バランス解析＆AI献立提案アプリ")

    api_key = get_api_key()

    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    # Gemini APIの初期化
    genai.configure(api_key=api_key)

    # 画像アップロード
    uploaded_file = st.file_uploader("料理写真をアップロードしてください", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="アップロードされた画像", use_column_width=True)

        # TODO: ここで画像解析・栄養解析の処理を実装
        st.info("画像解析・栄養解析はまだ未実装です。")

    # ユーザーからの質問入力欄
    user_input = st.text_area("AIに質問や献立提案を依頼してください")

    if st.button("質問する"):
        if user_input.strip() == "":
            st.warning("質問内容を入力してください。")
        else:
            try:
                model = genai.Ge
                model = genai.GenerateModel('gemini-2.0-flash-lite')

                response = model.generate_content(user_input)
                st.markdown("### AIの回答")
                st.write(response.text)
            except Exception as e:
                st.error(f"API呼び出しでエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
