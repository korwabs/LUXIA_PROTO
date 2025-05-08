import asyncio
import json
import os
import sys

# 경로 추가 (현재 디렉토리를 import path에 추가)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from tool_integration_setup import setup_suna_tools
from prompt_templates import PromptTemplates

async def test_integration():
    # 도구 설정
    project_id = "your-gcp-project-id"  # 실제 프로젝트 ID로 변경하세요
    
    # GCP 서비스 계정 키 파일 경로
    # 필요한 경우 실제 경로로 변경하세요
    credentials_path = os.path.join(os.path.dirname(parent_dir), "gcp-credentials", "service-account-key.json")
    
    # 도구 초기화
    tools = setup_suna_tools(project_id, credentials_path)
    
    if not tools.get("success", False):
        print(f"도구 설정 오류: {tools.get('message')}")
        return
    
    # 도구 인스턴스 가져오기
    tool_integration = tools["tools"]["tool_integration"]
    
    # BigQuery 데이터셋 탐색 테스트
    print("\n=== BigQuery 데이터셋 탐색 ===")
    result = await tool_integration.handle_tool_call("explore_bigquery_dataset", {
        "dataset_id": "analytics_data"
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # BigQuery 쿼리 제안 테스트
    print("\n=== BigQuery 쿼리 제안 ===")
    result = await tool_integration.handle_tool_call("get_bigquery_suggestions", {
        "intent": "일별 웹사이트 트래픽 추세 분석"
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 웹 여정 실행 테스트
    print("\n=== 웹 여정 실행 ===")
    journey_template = PromptTemplates.get_journey_template("https://example.com")
    
    result = await tool_integration.handle_tool_call("execute_web_journey", {
        "scenario": journey_template
    })
    print(f"여정 실행 결과: {result.get('success')}, {result.get('message')}")
    
    # 웹 여정 분석 테스트
    if result.get("success", False):
        print("\n=== 웹 여정 분석 ===")
        analysis_result = await tool_integration.handle_tool_call("analyze_web_journey", {
            "page_path": "/"
        })
        print(f"여정 분석 결과: {analysis_result.get('success')}, {analysis_result.get('message')}")
        
        # 주요 인사이트 출력
        if analysis_result.get("success", False) and "report" in analysis_result:
            print("\n=== 주요 UX/UI 개선 인사이트 ===")
            for issue in analysis_result["report"].get("issues", [])[:3]:
                print(f"- {issue.get('severity', '').upper()}: {issue.get('title')} - {issue.get('description')}")

if __name__ == "__main__":
    asyncio.run(test_integration())