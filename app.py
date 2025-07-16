import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px

# APIキーの取得（Secrets優先、なければ入力）
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except KeyError:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

# 画像解析：食材と栄養素をGemini APIに聞く
def analyze_image(image_file, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    image_bytes = image_file.getvalue()
    image_data = {"mime_type": image_file.type, "data": image_bytes}
    prompt = (
        "この料理画像に含まれる食材を推定し、"
        "食材ごとに「カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)」を表形式で教えてください。\n\n"
        "例:\nりんご：52, 0.3, 0.2, 14\nバナナ：89, 1.1, 0.3, 23"
    )
    response = model.generate_content([prompt, image_data])
    return response.text

# テキスト解析→DataFrame
def parse_nutrition_text(text):
    lines = [line for line in text.splitlines() if "：" in line or ":" in line]
    data = []
    for line in lines:
        line = line.replace(":", "：")  # 統一
        if "：" not in line:
            continue
        try:
            name, vals = line.split("：")
            vals = vals.replace("kcal","").replace("g","").replace(" ","")
            parts = vals.split(",")
            if len(parts) == 4:
                cal, prot, fat, carb = map(float, parts)
                data.append({
                    "食材": name,
                    "カロリー": cal,
                    "タンパク質": prot,
                    "脂質": fat,
                    "炭水化物": carb
                })
        except:
            continue
    return pd.DataFrame(data)

# マクロ栄養素円グラフ
def plot_macro_pie(df):
    if df.empty:
        return
    total = df[["タンパク質","脂質","炭水化物"]].sum().reset_index()
    total.columns = ["栄養素","量(g)"]
    fig = px.pie(total, names="栄養素", values="量(g)", title="マクロ栄養素割合")
    st.plotly_chart(fig, use_container_width=True)

# 今日の摂取合計計算
def sum_nutrition(log):
    df = pd.DataFrame(log)
    if df.empty:
        return None
    total = df[["カロリー","タンパク質","脂質","炭水化物"]].sum()
    return total

# 献立提案をGeminiに依頼
def generate_meal_plan(api_key, goal, nutrition_summary):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = (
        f"私は現在、今日これまでに以下の栄養素を摂取しています:\n"
        f"カロリー: {nutrition_summary['カロリー']:.1f} kcal, "
        f"タンパク質: {nutrition_summary['タンパク質']:.1f} g, "
        f"脂質: {nutrition_summary['脂質']:.1f} g, "
        f"炭水化物: {nutrition_summary['炭水化物']:.1f} g。\n"
        f"目標は「{goal}」です。\n"
        "この目標に合うよう、今日の残りの食事でおすすめの献立を提案してください。"
    )

    response = model.generate_content(prompt)
    return response.text

def main():
    st.title("🍽️ AI料理解析＆目標別献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーをSecretsに設定するか入力してください。")
        return

    # セッションステートで食事ログ管理
    if "meal_log" not in st.session_state:
        st.session_state.meal_log = []

    # 目標選択
    st.sidebar.header("目標設定")
    goal = st.sidebar.selectbox("あなたの栄養目標を選んでください",
                                ["健康維持", "筋肉増量", "減量", "バランスの良い食事"])

    # 左ペイン：画像アップロードと解析
    st.header("1. 料理画像をアップロードして栄養解析")
    uploaded = st.file_uploader("料理画像をアップロード", type=["jpg","jpeg","png"])
    if uploaded:
        st.image(uploaded, caption="アップロード画像", use_column_width=True)
        with st.spinner("解析中…"):
            try:
                result_text = analyze_image(uploaded, api_key)
                st.subheader("AI解析結果（テキスト）")
                st.text(result_text)

                df = parse_nutrition_text(result_text)
                if not df.empty:
                    st.subheader("解析結果（表形式）")
                    st.dataframe(df)

                    # 食事ログに追加ボタン
                    if st.button("この料理を食事履歴に追加"):
                        # 食事ログに追加
                        for _, row in df.iterrows():
                            st.session_state.meal_log.append(row.to_dict())
                        st.success("食事履歴に追加しました！")

                    plot_macro_pie(df)
                else:
                    st.warning("解析結果の形式が不正確です。")
            except Exception as e:
                st.error(f"解析に失敗しました: {e}")

    # 右ペイン：食事履歴と今日の摂取合計
    st.header("2. 今日の食事履歴")
    if st.session_state.meal_log:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log)

        total = sum_nutrition(st.session_state.meal_log)
        st.subheader("今日の摂取合計")
        st.write(f"カロリー: {total['カロリー']:.1f} kcal")
        st.write(f"タンパク質: {total['タンパク質']:.1f} g")
        st.write(f"脂質: {total['脂質']:.1f} g")
        st.write(f"炭水化物: {total['炭水化物']:.1f} g")

        plot_macro_pie(df_log)
    else:
        st.info("まだ食事履歴がありません。料理画像を解析して追加しましょう。")

    st.markdown("---")
    st.header("3. AIによる目標別献立提案")
    if st.button("今日の献立を提案してもらう"):
        if not st.session_state.meal_log:
            st.warning("まずは食事を追加してください。")
        else:
            with st.spinner("AIが献立を考えています…"):
                try:
                    total = sum_nutrition(st.session_state.meal_log)
                    advice = generate_meal_plan(api_key, goal, total)
                    st.subheader("献立提案")
                    st.write(advice)
                except Exception as e:
                    st.error(f"献立提案に失敗しました: {e}")

if __name__ == "__main__":
    main()
