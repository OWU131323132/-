import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.graph_objects as go
import re

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
        "\n例:\n"
        "| 食材          | カロリー(kcal) | タンパク質(g) | 脂質(g) | 炭水化物(g) |\n"
        "|---------------|----------------|---------------|---------|-------------|\n"
        "| りんご       | 52             | 0.3           | 0.2     | 14          |\n"
        "| バナナ       | 89             | 1.1           | 0.3     | 23          |"
    )
    response = model.generate_content(prompt)
    return response.text

def parse_nutrition_text(text):
    lines = text.strip().splitlines()
    data = []

    for line in lines:
        if '|' not in line:
            continue
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) < 5:
            continue
        # 合計や装飾文字の行を除外
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

def plot_macro_bar(nutrition_sum, goal_nutrition):
    # nutrition_sum, goal_nutritionはdictまたはpd.Seriesで以下キーを持つ:
    # 'カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)'
    categories = ['カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)']
    values = [nutrition_sum.get(cat, 0) for cat in categories]
    goals = [goal_nutrition.get(cat, 0) for cat in categories]
    percentages = [v/g*100 if g > 0 else 0 for v, g in zip(values, goals)]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=categories,
        x=percentages,
        orientation='h',
        text=[f"{values[i]:.1f} / {goals[i]}" for i in range(len(categories))],
        textposition='outside',
        marker_color='dodgerblue',
        name='達成度 (%)'
    ))

    fig.update_layout(
        title='今日の栄養素摂取の目標達成度',
        xaxis=dict(title='達成率 (%)', range=[0, max(110, max(percentages)*1.1)]),
        yaxis=dict(title='栄養素'),
        bargap=0.5,
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)

def sum_nutrition(log):
    if len(log) == 0:
        return None
    df = pd.DataFrame(log)
    return df[['カロリー(kcal)', 'タンパク質(g)', '脂質(g)', '炭水化物(g)']].sum()

def generate_meal_plan(api_key, goal, nutrition_summary):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

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
                    # テキストの表は隠すか折りたたみで表示
                    with st.expander("解析用テキスト（Markdown表形式）"):
                        st.code(text_result)

                    df = parse_nutrition_text(text_result)
                    if not df.empty:
                        st.subheader("解析結果（表形式）")
                        st.dataframe(df.style.format("{:.1f}"))
                        if st.button("この料理を食事履歴に追加"):
                            for _, row in df.iterrows():
                                st.session_state.meal_log.append(row.to_dict())
                            st.success("食事履歴に追加しました！")
                    else:
                        st.warning("解析結果の形式が不正確です。")
                except Exception as e:
                    st.error(f"解析に失敗しました: {e}")

    st.header("2. 食事履歴")
    if len(st.session_state.meal_log) == 0:
        st.info("まだ食事履歴はありません。栄養解析した料理を追加してください。")
    else:
        df_log = pd.DataFrame(st.session_state.meal_log)
        st.dataframe(df_log.style.format("{:.1f}"))

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

    # 目標に応じた理想栄養素（例、kcalは男女別個人差あるのでざっくり目安）
    goal_dict = {
        "筋肉を増やしたい": {
            'カロリー(kcal)': 2500,
            'タンパク質(g)': 150,
            '脂質(g)': 70,
            '炭水化物(g)': 300
        },
        "体重を減らしたい": {
            'カロリー(kcal)': 1800,
            'タンパク質(g)': 100,
            '脂質(g)': 50,
            '炭水化物(g)': 150
        },
        "健康的な食生活を維持したい": {
            'カロリー(kcal)': 2000,
            'タンパク質(g)': 120,
            '脂質(g)': 60,
            '炭水化物(g)': 220
        },
        "バランスの良い食事を取りたい": {
            'カロリー(kcal)': 2200,
            'タンパク質(g)': 130,
            '脂質(g)': 65,
            '炭水化物(g)': 250
        }
    }

    if st.button("栄養達成度を表示"):
        if len(st.session_state.meal_log) == 0:
            st.warning("まず食事履歴を追加してください。")
        else:
            nutrition_sum = sum_nutrition(st.session_state.meal_log)
            plot_macro_bar(nutrition_sum, goal_dict[goal])

    if st.button("AIに献立提案を依頼"):
        if len(st.session_state.meal_log) == 0:
            st.warning("まず食事履歴を追加してください。")
        else:
            with st.spinner("献立提案を生成中…"):
                try:
                    nutrition_sum = sum_nutrition(st.session_state.meal_log)
                    response = generate_meal_plan(api_key, goal, nutrition_sum)
                    st.subheader("🤖 AIの献立提案")
                    st.write(response)
                except Exception as e:
                    st.error(f"献立提案の生成に失敗しました: {e}")

if __name__ == "__main__":
    main()
