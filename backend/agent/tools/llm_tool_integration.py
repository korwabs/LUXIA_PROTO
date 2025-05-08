import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Callable

class LLMToolIntegration:
    def __init__(self, sandbox_browser_tool, bigquery_tool):
        """
        LLM 도구 통합 클래스 초기화
        
        Args:
            sandbox_browser_tool: SandboxBrowserTool 인스턴스
            bigquery_tool: BigQueryTool 인스턴스
        """
        self.browser_tool = sandbox_browser_tool
        self.bigquery_tool = bigquery_tool
        self.journey_scenario = None
    
    def register_tools_with_llm(self, tool_registry_function: Callable):
        """
        LLM에 도구를 등록합니다.
        
        Args:
            tool_registry_function: 도구를 등록하는 콜백 함수
        """
        # BigQuery 도구 등록
        tool_registry_function({
            "type": "function",
            "function": {
                "name": "run_bigquery",
                "description": "BigQuery에서 SQL 쿼리를 실행하여 데이터를 분석합니다. 웹 분석, 제품 데이터, 사용자 행동 등에 관한 데이터를 조회할 때 사용하세요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "실행할 SQL 쿼리. 쿼리는 BigQuery 문법을 따라야 합니다."
                        },
                        "params": {
                            "type": "object",
                            "description": "쿼리 매개변수 (선택적). 키-값 쌍으로 구성됩니다.",
                            "additionalProperties": True
                        }
                    },
                    "required": ["query"]
                }
            }
        })
        
        tool_registry_function({
            "type": "function",
            "function": {
                "name": "explore_bigquery_dataset",
                "description": "BigQuery 데이터셋의 테이블 및 스키마 정보를 탐색합니다. 사용 가능한 데이터와 테이블 구조를 파악할 때 사용하세요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "탐색할 데이터셋 ID (예: 'analytics_data')"
                        },
                        "max_tables": {
                            "type": "integer",
                            "description": "반환할 최대 테이블 수 (기본값: 100)",
                            "default": 100
                        }
                    },
                    "required": ["dataset_id"]
                }
            }
        })
        
        tool_registry_function({
            "type": "function",
            "function": {
                "name": "get_bigquery_suggestions",
                "description": "사용자 의도에 기반한 BigQuery 쿼리 제안을 생성합니다. 분석 방향이 명확하지 않을 때 적절한 쿼리 예시를 얻기 위해 사용하세요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "사용자의 분석 의도 설명 (예: '일별 웹사이트 트래픽 추세 분석')"
                        }
                    },
                    "required": ["intent"]
                }
            }
        })
        
        # 웹 자동화 시나리오 도구 등록
        tool_registry_function({
            "type": "function",
            "function": {
                "name": "execute_web_journey",
                "description": "웹사이트 사용자 여정을 자동화하여 실행합니다. 로그인, 탐색, 페이지 분석 등의 단계로 구성된 시나리오를 실행하여 사용자 경험을 테스트합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scenario": {
                            "type": "array",
                            "description": "실행할 시나리오 단계 목록",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "description": "수행할 동작 유형",
                                        "enum": ["navigate", "click", "input", "wait", "scroll", "take_screenshot", "analyze_page", "login", "navigate_to_mypage"]
                                    },
                                    "critical": {
                                        "type": "boolean",
                                        "description": "이 단계가 실패하면 시나리오를 중단할지 여부",
                                        "default": False
                                    },
                                    "post_delay": {
                                        "type": "number",
                                        "description": "이 단계 완료 후 대기 시간(초)",
                                        "default": 1
                                    }
                                },
                                "required": ["action"],
                                "additionalProperties": True
                            }
                        }
                    },
                    "required": ["scenario"]
                }
            }
        })
        
        tool_registry_function({
            "type": "function",
            "function": {
                "name": "analyze_web_journey",
                "description": "실행된 웹 사용자 여정을 분석하고 UX/UI 개선 인사이트를 생성합니다. 여정을 먼저 execute_web_journey로 실행한 후 사용하세요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_path": {
                            "type": "string",
                            "description": "분석할 페이지 경로 (예: '/products'). 지정하지 않으면 여정의 첫 번째 URL에서 추출합니다."
                        }
                    }
                }
            }
        })
    
    async def handle_tool_call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM의 도구 호출을 처리합니다.
        
        Args:
            tool_name (str): 호출할 도구 이름
            params (Dict): 도구 호출 매개변수
            
        Returns:
            Dict: 도구 호출 결과
        """
        try:
            # BigQuery 도구 호출 처리
            if tool_name == "run_bigquery":
                query = params.get("query", "")
                query_params = params.get("params", {})
                
                return await self.bigquery_tool.run_query(query, query_params)
            
            elif tool_name == "explore_bigquery_dataset":
                dataset_id = params.get("dataset_id", "")
                max_tables = params.get("max_tables", 100)
                
                return await self.bigquery_tool.explore_dataset(dataset_id, max_tables)
            
            elif tool_name == "get_bigquery_suggestions":
                intent = params.get("intent", "")
                
                return await self.bigquery_tool.get_query_suggestions(intent)
            
            # 웹 자동화 시나리오 도구 호출 처리
            elif tool_name == "execute_web_journey":
                scenario = params.get("scenario", [])
                
                if not self.journey_scenario:
                    from analytics_integrator import AnalyticsIntegrator
                    analytics_integrator = AnalyticsIntegrator(self.bigquery_tool.project_id)
                    from journey_scenario import JourneyScenario
                    self.journey_scenario = JourneyScenario(self.browser_tool, analytics_integrator)
                
                return await self.journey_scenario.execute_scenario(scenario)
            
            elif tool_name == "analyze_web_journey":
                page_path = params.get("page_path")
                
                if not self.journey_scenario:
                    return {
                        "success": False,
                        "message": "먼저 execute_web_journey를 호출하여 여정을 실행해야 합니다."
                    }
                
                return await self.journey_scenario.analyze_journey(page_path)
            
            else:
                return {
                    "success": False,
                    "message": f"알 수 없는 도구 이름: {tool_name}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"도구 호출 오류: {str(e)}"
            }