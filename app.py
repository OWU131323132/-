import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import re

def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    else:
        return st.text_input("Gemini APIキーを入力してください:", type="password")

def parse_nutrition_text(text):
    lines = [line.strip() for line in text.splitlines() if re.match(r'^\|.*\|$', line.strip())]
    if len(lines) < 3:
        return pd.DataFrame()
    header = [h.strip() for h in lines[0].strip('|').split('|')]
    data = []
    for line in lines[2:]:
        row = [r.strip() for r in line.strip('|').split('|')]
        if any(k in row[0] for k in ['合計', '-----', '----']):
            continue
        if len(row) != len(header):
            continue
        data.append(row)
    df = pd.DataFrame(data, columns=header)
    def clean_num(x):
        if isinstance(x, str):
            x = x.replace('約', '').replace(',', '').strip()
            try:
                return float(x)
            except:
                return 0.0
        elif pd.isna(x):
            return 0.0
        return float(x)
    for col in df.columns[1:]:
        df[col] = df[col].apply(clean_num)
    return df

def sum_nutrition(log_df):
    if log_df.empty:
        return None
    numeric_cols = log_df.columns[1:]
    sums = log_df[numeric_cols].sum()
    return sums

def plot_nutrition_bar(nutrition_sum, goal_dict):
    if nutrition_sum is None or len(nutrition_sum) == 0:
        st.info("栄養摂取合計データがありません。")
        return
    nutrients = list(goal_dict.keys())
    goal_vals = [goal_dict[n] for n in nutrients]
    actual_vals = [nutrition_sum.get(n, 0) for n in nutrients]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=nutrients,
        x=goal_vals,
        name='目標値',
        orientation='h',
        marker=dict(color='lightgray'),
        opacity=0.6,
    ))
    fig.add_trace(go.Bar(
        y=nutrients,
        x=actual_vals,
        name='摂取量',
        orientation='h',
        marker=dict(color='steelblue')
    ))
    max_x = max(max(goal_vals), max(actual_vals)) * 1.2
    fig.update_layout(
        barmode='overlay',
        title='今日の栄養摂取状況',
        xaxis_title='量',
        yaxis_title='栄養素',
        xaxis=dict(range=[0, max_x]),
        height=400,
        margin=dict(l=130)
    )
    st.plotly_chart(fig, use_container_width=True)

def get_daily_goal():
    return {
        "カロリー(kcal)": 2500,
        "タンパク質(g)": 60,
        "脂質(g)": 70,
        "炭水化物(g)": 310,
        "食物繊維(g)": 20,
        "カルシウム(mg)": 650,
        "鉄分(mg)": 7.5,
        "ビタミンC(mg)": 100,
        "ナトリウム(mg)": 2400,
    }

def main():
    st.title("料理栄養解析＆AI献立提案アプリ")

    api_key = get_api_key()
    if not api_key:
        st.warning("APIキーを設定してください。")
        return

    genai.configure(api_key=api_key)

    if "meal_log" not in st.session_state:
        st.session_state.meal_log = pd.DataFrame()

    st.header("▼ 料理名を入力して栄養情報を取得")

    dish_name = st.text_input("料理名を入力してください（例: 鶏の照り焼き）")

    if st.button("栄養情報を取得して食事履歴に追加"):
        if not dish_name.strip():
            st.warning("料理名を入力してください。")
        else:
            try:
                prompt = (
                    f"以下の料理の栄養情報を表形式で教えてください。"
                    f"食材、カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)、食物繊維(g)、カルシウム(mg)、鉄分(mg)、ビタミンC(mg)、ナトリウム(mg)を含めて。"
                    f"\n料理名: {dish_name}\n"
                    f"Markdown形式のテーブルでお願いします。"
                )

                response = genai.generate_text(
                    model="gemini-2.0-flash-lite",
                    prompt=prompt,
                )
                text = response.candidates[0].output

                st.markdown("### 取得した栄養情報（AI出力）")
                st.code(text)

                df = parse_nutrition_text(text)
                if df.empty:
                    st.error("AIからの栄養情報解析に失敗しました。")
                else:
                    st.session_state.meal_log = pd.concat([st.session_state.meal_log, df], ignore_index=True)
                    st.success("食事履歴に追加しました。")
                    st.dataframe(st.session_state.meal_log.style.format("{:.1f}", na_rep="0"))

            except Exception as e:
                st.error(f"栄養情報取得でエラーが発生しました: {e}")

    st.header("▼ 今日の食事履歴")
    if st.session_state.meal_log.empty:
        st.info("まだ食事履歴がありません。")
    else:
        st.dataframe(st.session_state.meal_log.style.format("{:.1f}", na_rep="0"))
        nutrition_sum = sum_nutrition(st.session_state.meal_log)
        if nutrition_sum is not None:
            st.subheader("今日の摂取合計")
            for k, v in nutrition_sum.items():
                st.write(f"{k}: {v:.1f}")

            goal_dict = get_daily_goal()
            plot_nutrition_bar(nutrition_sum, goal_dict)

    st.header("▼ AIに献立提案を依頼")
    user_goal = st.selectbox("あなたの目標を選択してください", ["体重維持", "筋肉増強", "ダイエット", "健康維持"])
    user_input = st.text_area("質問や献立提案を入力してください（例: 高タンパクな夕食メニューを教えて）")

    if st.button("献立提案を取得"):
        if not api_key:
            st.error("APIキーが設定されていません。")
        elif not user_input.strip():
            st.warning("質問内容を入力してください。")
        else:
            try:
                nutrition_sum = sum_nutrition(st.session_state.meal_log)
                nutrition_info_str = str(nutrition_sum.to_dict()) if nutrition_sum is not None else "なし"
                prompt = (
                    f"ユーザーの今日の食事履歴の栄養摂取合計:\n{nutrition_info_str}\n"
                    f"目標: {user_goal}\n"
                    f"この情報をもとに、残りの食事で摂るべき献立を提案してください。\n"
                    f"ユーザーの質問:\n{user_input}"
                )

                response = genai.generate_text(
                    model="gemini-2.0-flash-lite",
                    prompt=prompt,
                )
                st.subheader("🤖 AIの献立提案")
                st.write(response.candidates[0].output)

            except Exception as e:
                st.error(f"AI献立提案の生成に失敗しました: {e}")

if __name__ == "__main__":
    main()
