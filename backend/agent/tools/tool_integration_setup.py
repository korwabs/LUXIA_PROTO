import os
import json
import asyncio
from typing import Dict, List, Any, Optional

def setup_suna_tools(
    project_id: str,
    credentials_path: Optional[str] = None,
    thread_manager=None,
    thread_id=None
):
    """
    SUNA AI 프레임워크에서 사용할 BigQuery 및 웹 자동화 도구 설정
    
    Args:
        project_id (str): GCP 프로젝트 ID
        credentials_path (str, optional): GCP 서비스 계정 키 파일 경로
        thread_manager: SUNA AI 스레드 관리자 객체
        thread_id (str, optional): 도구를 연결할 스레드 ID
        
    Returns:
        Dict: 설정된 도구 정보
    """
    from sb_browser_tool import SandboxBrowserTool
    from bigquery_tool import BigQueryTool
    from llm_tool_integration import LLMToolIntegration
    
    # SandboxBrowserTool 초기화
    browser_tool = SandboxBrowserTool(project_id, thread_id, thread_manager)
    
    # BigQueryTool 초기화
    bigquery_tool = BigQueryTool(project_id, credentials_path)
    
    # LLM 도구 통합 초기화
    tool_integration = LLMToolIntegration(browser_tool, bigquery_tool)
    
    # 도구 등록 함수 (SUNA AI 프레임워크에 맞게 수정 필요)
    def register_tool(tool_def):
        if thread_manager and thread_id:
            # SUNA AI 프레임워크에 도구 등록
            thread_manager.register_tool(thread_id, tool_def)
        else:
            print(f"도구 정의 등록: {tool_def['function']['name']}")
    
    # LLM에 도구 등록
    tool_integration.register_tools_with_llm(register_tool)
    
    # 도구 호출 핸들러 설정 (SUNA AI 프레임워크에 맞게 수정 필요)
    async def handle_tool_call(call_data):
        tool_name = call_data.get("name")
        params = call_data.get("parameters", {})
        
        result = await tool_integration.handle_tool_call(tool_name, params)
        return result
    
    # SUNA AI 프레임워크에 핸들러 등록
    if thread_manager and thread_id:
        thread_manager.set_tool_handler(thread_id, handle_tool_call)
    
    return {
        "success": True,
        "message": "SUNA AI 도구 통합 설정 완료",
        "tools": {
            "browser_tool": browser_tool,
            "bigquery_tool": bigquery_tool,
            "tool_integration": tool_integration
        }
    }