import streamlit as st
import pandas as pd
import openai
import json

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="AI 프로젝트 공수 산정 시스템", layout="wide")
st.title("📊 AI 프로젝트 공수 산정 시스템")
st.caption("포켓CU 고도화 기준 매트릭스를 활용한 자동 공수 산정 및 WBS 생성 프로그램")

st.markdown("---")

# 🔥 [수정 포인트] 찾기 힘들었던 API 입력창을 화면 정중앙 맨 위로 배치했습니다.
st.subheader("🔑 1단계: OpenAI API Key 입력")
api_key = st.text_input(
    "사용자의 OpenAI API Key(sk-...로 시작하는 값)를 입력하고 엔터를 눌러주세요.", 
    type="password",
    help="AI가 상세 과업 분해(WBS)와 산정근거 문장을 창작하는 데 사용됩니다."
)

st.markdown("---")

# 2. 엑셀 분석용 핵심 생산성 매트릭스 정의
PRODUCTIVITY_MATRIX = {
    "신규": {1: 5.0, 2: 7.0, 3: 9.0},
    "변경": {1: 4.0, 2: 5.0, 3: 7.0}
}

# 3. 파일 업로드 UI (화면 중앙 배치)
st.subheader("📂 2단계: 과업 범위 엑셀 파일 업로드")
uploaded_file = st.file_uploader(
    "추진과제, 개발요건, 개발요건(Level2), 비고, 구분, 난이도, 본수 컬럼이 포함된 파일을 드래그하세요.", 
    type=["xlsx", "csv"]
)

if uploaded_file and api_key:
    # OpenAI 클라이언트 초기화
    openai.api_key = api_key
    
    # 파일 읽기
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.success("✅ 파일 업로드 성공! 실시간 분석을 진행합니다.")
    
    # 4. 필수 컬럼 체크
    required_cols = ["추진과제", "개발요건", "개발요건(Level2)", "비고", "구분", "난이도", "본수"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ 엑셀 파일에 다음 필수 컬럼 헤더가 누락되었습니다: {missing_cols}")
    else:
        # 5. Python 기반 기본 수식 및 생산성 자동 계산
        calculated_data = []
        
        for idx, row in df.iterrows():
            gubun = str(row["구분"]).strip()
            try:
                level = int(float(row["난이도"]))
                qty = float(row["본수"])
            except:
                level = 0
                qty = 0.0
                
            productivity = PRODUCTIVITY_MATRIX.get(gubun, {}).get(level, 0.0)
            calc_md = qty * productivity
            test_md = round(calc_md * 0.2, 2)
            
            calculated_data.append({
                "추진과제": row["추진과제"],
                "개발요건": row["개발요건"],
                "개발요건(Level2)": row["개발요건(Level2)"],
                "비고": row["비고"],
                "구분": gubun,
                "난이도": level,
                "본수": qty,
                "생산성(MD/본)": productivity,
                "산출 공수(MD)": calc_md,
                "테스트공수(MD)": test_md,
                "총공수(MD)": calc_md + test_md
            })
            
        res_df = pd.DataFrame(calculated_data)
        
        # 6. AI 연동 - WBS 및 산정근거 문장 생성
        st.markdown("---")
        st.subheader("🤖 3단계: AI 기반 WBS 및 산정근거 문장 생성")
        progress_bar = st.progress(0)
        
        wbs_list = []
        basis_list = []
        
        for i, row in res_df.iterrows():
            user_prompt = f"""
            개발요건: {row['개발요건']}
            상세요건(Level2): {row['개발요건(Level2)']}
            비고: {row['비고']}
            구분: {row['구분']}
            난이도: {row['난이도']}
            본수: {row['본수']}
            산출 공수(MD): {row['산출 공수(MD)']}
            
            위 정보를 바탕으로 SI 프로젝트 기준에 맞는 구체적인 '작업분해(WBS)' 3~5줄과 '산정근거' 1줄을 JSON 형식으로 작성해줘. 
            반드시 아래 JSON 포맷만 응답해야 해:
            {{"wbs": "- 작업1\\n- 작업2\\n- 작업3", "basis": "산정근거 내용"}}
            """
            
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 20년 경력의 SI PM이며 공수 산정 전문가입니다. 반드시 지정된 JSON 포맷으로만 답변하세요."},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                ai_res = json.loads(response.choices[0].message.content)
                wbs_list.append(ai_res.get("wbs", "- 분석 및 설계\n- 개발 및 단위테스트"))
                basis_list.append(ai_res.get("basis", "기본 생산성 지표 반영 산정"))
            except Exception as e:
                wbs_list.append("- 분석 및 설계\n- 로직 구현\n- 테스트")
                basis_list.append("AI 통신 오류로 기본 근거 대체")
                
            progress_bar.progress((i + 1) / len(res_df))
            
        res_df["작업분해(WBS)"] = wbs_list
        res_df["산정근거"] = basis_list
        
        # 7. 최종 결과 화면 출력
        st.subheader("📊 산정 완료 데이터 내역")
        st.dataframe(res_df)
        
        # 8. 프로젝트 총괄 요약 계산
        total_dev = res_df["산출 공수(MD)"].sum()
        total_test = res_df["테스트공수(MD)"].sum()
        pm_md = round(total_dev * 0.1, 2)
        buffer_md = round(total_dev * 0.1, 2)
        final_total = total_dev + total_test + pm_md + buffer_md
        final_mm = round(final_total / 20, 2)
        
        st.markdown("---")
        st.subheader("📉 프로젝트 공수 종합 요약")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 개발 공수", f"{total_dev:.1f} MD")
        col2.metric("총 테스트 공수", f"{total_test:.1f} MD")
        col3.metric("PM/PL 관리 공수 (10%)", f"{pm_md:.1f} MD")
        col4.metric("프로젝트 버퍼 (10%)", f"{buffer_md:.1f} MD")
        
        st.info(f"🚀 **최종 프로젝트 총공수: {final_total:.1f} MD / MM 환산 (월 20일 기준): {final_mm:.2f} MM**")
        
        # 9. 엑셀 다운로드 기능
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8-sig')
            
        csv_data = convert_df(res_df)
        st.download_button(
            label="📥 산정 완료 엑셀(CSV) 다운로드",
            data=csv_data,
            file_name="AI_공수산정_결과리포트.csv",
            mime="text/csv"
        )
elif uploaded_file and not api_key:
    st.warning("⚠️ 데이터를 분석하려면 상단의 '1단계'에 OpenAI API Key를 반드시 입력하셔야 합니다.")