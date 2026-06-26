import sys
import subprocess

# 🔥 [치트키] 시스템에 openai와 openpyxl 라이브러리가 없으면 코드가 실행되면서 자동으로 설치합니다.
try:
    import openai
except ModuleNotFoundError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai", "openpyxl"])
    import openai

import streamlit as st
import pandas as pd
import json

# 1. 페이지 제목 및 레이아웃 설정
st.set_page_config(page_title="AI 프로젝트 공수 산정 시스템", layout="wide")
st.title("📊 AI 프로젝트 공수 산정 시스템")
st.caption("포켓CU 고도화 기준 매트릭스를 활용한 자동 공수 산정 및 WBS 생성 프로그램")

st.markdown("---")

# 2. 화면 중앙 최상단에 API 입력창 배치
st.subheader("🔑 1단계: OpenAI API Key 입력")
api_key = st.text_input(
    "사용자의 OpenAI API Key(sk-...로 시작하는 값)를 입력하고 엔터를 눌러주세요.", 
    type="password"
)

st.markdown("---")

# 3. 엑셀 분석용 핵심 생산성 매트릭스 정의
PRODUCTIVITY_MATRIX = {
    "신규": {1: 5.0, 2: 7.0, 3: 9.0},
    "변경": {1: 4.0, 2: 5.0, 3: 7.0}
}

# 4. 파일 업로드 UI (화면 중앙 배치)
st.subheader("📂 2단계: 과업 범위 엑셀 파일 업로드")
uploaded_file = st.file_uploader(
    "추진과제, 개발요건, 개발요건(Level2), 비고, 구분, 난이도, 본수 컬럼이 포함된 파일을 드래그하세요.", 
    type=["xlsx", "csv"]
)

if uploaded_file and api_key:
    openai.api_key = api_key
    
    # 파일 읽기 (CSV 및 Excel 대응)
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.success("✅ 파일 업로드 성공! 실시간 분석을 진행합니다.")
    
    # 필수 컬럼 체크
    required_cols = ["추진과제", "개발요건", "개발요건(Level2)", "비고", "구분", "난이도", "본수"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ 엑셀 파일에 다음 필수 컬럼 헤더가 누락되었습니다: {missing_cols}")
    else:
        # 5. 생산성 및 공수 자동 계산 (하이브리드 엔진)
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
            user_prompt = f"개발요건: {row['개발요건']}\n상세요건: {row['개발요건(Level2)']}\n비고: {row['비고']}\n구분: {row['구분']}\n난이도: {row['난이도']}\n본수: {row['본수']}\n\n위 정보를 바탕으로 SI 프로젝트 기준에 맞는 구체적인 '작업분해(WBS)' 3~5줄과 '산정근거' 1줄을 JSON 형식으로 작성해줘. 포맷: {{\"wbs\": \"- 작업1\\n- 작업2\", \"basis\": \"근거\"}}"
            
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 20년 경력의 SI PM입니다. 지정된 JSON 포맷으로만 답변하세요."},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                ai_res = json.loads(response.choices[0].message.content)
                wbs_list.append(ai_res.get("wbs", "- 분석 및 설계\n- 개발"))
                basis_list.append(ai_res.get("basis", "기본 생산성 반영"))
            except:
                wbs_list.append("- 분석 및 설계\n- 로직 구현")
                basis_list.append("기본 지표 산정")
                
            progress_bar.progress((i + 1) / len(res_df))
            
        res_df["작업분해(WBS)"] = wbs_list
        res_df["산정근거"] = basis_list
        
        # 7. 화면 출력 및 대시보드
        st.subheader("📊 산정 완료 데이터 내역")
        st.dataframe(res_df)
        
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
        
        # 8. 📥 결과 다운로드
        csv_data = res_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 산정 완료 엑셀(CSV) 다운로드", data=csv_data, file_name="AI_공수산정_결과.csv", mime="text/csv")
elif uploaded_file and not api_key:
    st.warning("⚠️ 상단의 '1단계'에 OpenAI API Key를 입력하셔야 분석이 시작됩니다.")
    