import json
import asyncio
import datetime
import base64
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

class JourneyScenario:
    def __init__(self, browser_tool, analytics_integrator=None):
        """
        웹 자동화 시나리오 클래스 초기화
        
        Args:
            browser_tool: SandboxBrowserTool 인스턴스
            analytics_integrator (optional): AnalyticsIntegrator 인스턴스
        """
        self.browser_tool = browser_tool
        self.analytics_integrator = analytics_integrator
        self.journey_data = {
            "start_time": datetime.datetime.now().isoformat(),
            "steps": [],
            "errors": [],
            "duration": 0,
            "success": False,
            "ui_metrics": {},
            "a11y_results": {},
            "screenshots": []
        }
    
    async def execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 단계를 실행합니다.
        
        Args:
            step (Dict): 실행할 단계 정보
            
        Returns:
            Dict: 단계 실행 결과
        """
        step_start_time = datetime.datetime.now()
        step_type = step.get("action")
        step_data = {"type": step_type, "start_time": step_start_time.isoformat()}
        
        try:
            # 단계 유형에 따른 처리
            if step_type == "navigate":
                url = step.get("url")
                result = await self.browser_tool.browser_navigate_to(url)
                step_data.update({
                    "url": url,
                    "success": result.success,
                    "message": result.message
                })
            
            elif step_type == "click":
                selector = step.get("selector")
                element_desc = step.get("description", "요소")
                
                # 먼저 요소가 보이도록 스크롤
                if step.get("scroll_into_view", True):
                    await self.browser_tool.browser_evaluate(f"""
                        () => {{
                            const element = document.querySelector("{selector}");
                            if (element) element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    """)
                    await asyncio.sleep(1)
                
                # 요소 클릭
                result = await self.browser_tool.browser_evaluate(f"""
                    async () => {{
                        try {{
                            const element = document.querySelector("{selector}");
                            if (!element) return {{ success: false, message: "요소를 찾을 수 없음" }};
                            
                            element.click();
                            return {{ success: true, message: "요소 클릭 성공" }};
                        }} catch (error) {{
                            return {{ success: false, message: error.toString() }};
                        }}
                    }}
                """)
                
                step_data.update({
                    "selector": selector,
                    "element_description": element_desc,
                    "success": result.get("success", False),
                    "message": result.get("message", "")
                })
            
            elif step_type == "input":
                selector = step.get("selector")
                text = step.get("text", "")
                element_desc = step.get("description", "입력 필드")
                
                # 요소가 보이도록 스크롤
                if step.get("scroll_into_view", True):
                    await self.browser_tool.browser_evaluate(f"""
                        () => {{
                            const element = document.querySelector("{selector}");
                            if (element) element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    """)
                    await asyncio.sleep(1)
                
                # 텍스트 입력
                result = await self.browser_tool.browser_evaluate(f"""
                    async () => {{
                        try {{
                            const element = document.querySelector("{selector}");
                            if (!element) return {{ success: false, message: "요소를 찾을 수 없음" }};
                            
                            // 기존 내용 지우기
                            element.value = "";
                            
                            // 새 내용 입력
                            element.value = "{text}";
                            
                            // 입력 이벤트 발생
                            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            
                            return {{ success: true, message: "텍스트 입력 성공" }};
                        }} catch (error) {{
                            return {{ success: false, message: error.toString() }};
                        }}
                    }}
                """)
                
                step_data.update({
                    "selector": selector,
                    "element_description": element_desc,
                    "text": text,
                    "success": result.get("success", False),
                    "message": result.get("message", "")
                })
            
            elif step_type == "wait":
                seconds = step.get("seconds", 3)
                await self.browser_tool.browser_wait(seconds)
                
                step_data.update({
                    "seconds": seconds,
                    "success": True,
                    "message": f"{seconds}초 대기 완료"
                })
            
            elif step_type == "scroll":
                direction = step.get("direction", "down")
                distance = step.get("distance", 300)
                
                if direction == "down":
                    result = await self.browser_tool.browser_scroll_down(distance)
                elif direction == "up":
                    result = await self.browser_tool.browser_scroll_up(distance)
                
                step_data.update({
                    "direction": direction,
                    "distance": distance,
                    "success": result.success if hasattr(result, 'success') else False,
                    "message": result.message if hasattr(result, 'message') else ""
                })
            
            elif step_type == "take_screenshot":
                result = await self.browser_tool.browser_capture_full_page_screenshot()
                
                screenshot_id = len(self.journey_data["screenshots"]) + 1
                step_data.update({
                    "screenshot_id": screenshot_id,
                    "success": result.get("success", False),
                    "message": result.get("message", "")
                })
                
                if result.get("success", False) and result.get("data"):
                    self.journey_data["screenshots"].append({
                        "id": screenshot_id,
                        "data": result["data"],
                        "timestamp": datetime.datetime.now().isoformat(),
                        "dimensions": result.get("dimensions", {})
                    })
            
            elif step_type == "analyze_page":
                structure_result = await self.browser_tool.browser_analyze_page_structure()
                metrics_result = await self.browser_tool.browser_extract_ui_metrics()
                a11y_result = await self.browser_tool.browser_run_a11y_audit()
                
                step_data.update({
                    "page_structure": structure_result.get("structure", {}),
                    "ui_metrics": metrics_result.get("metrics", {}),
                    "a11y_results": a11y_result.get("results", {}),
                    "success": structure_result.get("success", False) and metrics_result.get("success", False),
                    "message": "페이지 분석 완료"
                })
                
                # 전체 여정 데이터에 UI 메트릭과 접근성 결과 저장
                if metrics_result.get("success", False):
                    self.journey_data["ui_metrics"] = metrics_result.get("metrics", {})
                
                if a11y_result.get("success", False):
                    self.journey_data["a11y_results"] = a11y_result.get("results", {})
            
            elif step_type == "login":
                url = step.get("url")
                username = step.get("username")
                password = step.get("password")
                username_selector = step.get("username_selector")
                password_selector = step.get("password_selector")
                submit_selector = step.get("submit_selector")
                cookie_selector = step.get("cookie_selector")
                
                result = await self.browser_tool.browser_login(
                    url, username_selector, password_selector,
                    submit_selector, username, password,
                    cookie_selector, 5000
                )
                
                step_data.update({
                    "url": url,
                    "username_selector": username_selector,
                    "password_selector": password_selector,
                    "submit_selector": submit_selector,
                    "username": username,
                    "success": result.get("success", False),
                    "message": result.get("message", ""),
                    "current_url": result.get("current_url", "")
                })
            
            elif step_type == "navigate_to_mypage":
                selector = step.get("selector")
                text = step.get("text")
                
                result = await self.browser_tool.browser_navigate_to_mypage(selector, text)
                
                step_data.update({
                    "selector": selector,
                    "text": text,
                    "success": result.get("success", False),
                    "message": result.get("message", ""),
                    "url": result.get("url", "")
                })
            
            else:
                step_data.update({
                    "success": False,
                    "message": f"알 수 없는 단계 유형: {step_type}"
                })
        
        except Exception as e:
            step_data.update({
                "success": False,
                "message": f"단계 실행 오류: {str(e)}"
            })
        
        # 단계 종료 시간 및 소요 시간 계산
        step_end_time = datetime.datetime.now()
        step_duration = (step_end_time - step_start_time).total_seconds()
        
        step_data.update({
            "end_time": step_end_time.isoformat(),
            "duration_seconds": step_duration
        })
        
        # 오류 발생 시 오류 목록에 추가
        if not step_data.get("success", False):
            self.journey_data["errors"].append({
                "step": step_type,
                "step_index": len(self.journey_data["steps"]),
                "message": step_data.get("message", ""),
                "element": step_data.get("selector", step_data.get("url", "")),
                "timestamp": step_end_time.isoformat()
            })
        
        # 여정 단계 목록에 추가
        self.journey_data["steps"].append(step_data)
        
        return step_data
    
    async def execute_scenario(self, scenario: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        전체 시나리오를 실행합니다.
        
        Args:
            scenario (List[Dict]): 실행할 시나리오 단계 목록
            
        Returns:
            Dict: 시나리오 실행 결과
        """
        # 시작 시간 기록
        scenario_start_time = datetime.datetime.now()
        self.journey_data["start_time"] = scenario_start_time.isoformat()
        self.journey_data["steps"] = []
        self.journey_data["errors"] = []
        
        # 각 단계 순차적으로 실행
        for i, step in enumerate(scenario):
            print(f"단계 {i+1}/{len(scenario)} 실행 중: {step.get('action', '알 수 없는 동작')}")
            
            # 단계 실행
            step_result = await self.execute_step(step)
            
            # 실패한 단계가 중요 단계인 경우 시나리오 중단
            if not step_result.get("success", False) and step.get("critical", False):
                print(f"중요 단계 실패로 시나리오 중단: {step_result.get('message', '')}")
                break
            
            # 다음 단계 실행 전 잠시 대기 (페이지 안정화를 위해)
            await asyncio.sleep(step.get("post_delay", 1))
        
        # 종료 시간 및 총 소요 시간 계산
        scenario_end_time = datetime.datetime.now()
        duration_seconds = (scenario_end_time - scenario_start_time).total_seconds()
        
        self.journey_data.update({
            "end_time": scenario_end_time.isoformat(),
            "duration": duration_seconds,
            "success": len(self.journey_data["errors"]) == 0,
            "path": self._extract_journey_path()
        })
        
        # 결과 반환
        return {
            "success": self.journey_data["success"],
            "message": "시나리오 실행 완료",
            "journey_data": self.journey_data
        }
    
    def _extract_journey_path(self) -> str:
        """
        여정 경로 문자열을 추출합니다.
        
        Returns:
            str: 여정 경로 문자열
        """
        urls = []
        
        for step in self.journey_data["steps"]:
            if step["type"] in ["navigate", "login"] and "url" in step:
                urls.append(step["url"])
            elif step["type"] == "navigate_to_mypage" and "url" in step:
                urls.append(step["url"])
        
        return " -> ".join(urls)
    
    async def analyze_journey(self, page_path: str = None) -> Dict[str, Any]:
        """
        완료된 여정을 분석하고 인사이트를 도출합니다.
        
        Args:
            page_path (str, optional): 분석할 페이지 경로
            
        Returns:
            Dict: 분석 결과
        """
        if not self.analytics_integrator:
            return {
                "success": False,
                "message": "analytics_integrator가 설정되지 않아 분석을 수행할 수 없습니다."
            }
        
        # 페이지 경로가 지정되지 않은 경우 여정의 첫 번째 URL에서 추출
        if not page_path and self.journey_data["steps"]:
            for step in self.journey_data["steps"]:
                if step["type"] in ["navigate", "login"] and "url" in step:
                    try:
                        parsed_url = urlparse(step["url"])
                        page_path = parsed_url.path
                        break
                    except:
                        pass
        
        if not page_path:
            return {
                "success": False,
                "message": "분석할 페이지 경로를 찾을 수 없습니다."
            }
        
        # GA 데이터와 비교 분석
        comparison_result = await self.analytics_integrator.compare_user_journey_with_analytics(
            self.journey_data, page_path, 30
        )
        
        if not comparison_result.get("success", False):
            return {
                "success": False,
                "message": f"여정 데이터 분석 실패: {comparison_result.get('message', '')}"
            }
        
        # UX 개선 보고서 생성
        report_result = await self.analytics_integrator.generate_ux_improvement_report(
            self.journey_data,
            comparison_result,
            {"results": self.journey_data.get("a11y_results", {})}
        )
        
        if not report_result.get("success", False):
            return {
                "success": False,
                "message": f"UX 개선 보고서 생성 실패: {report_result.get('message', '')}"
            }
        
        return {
            "success": True,
            "message": "여정 분석 및 UX 개선 보고서 생성 완료",
            "comparison": comparison_result.get("comparison", {}),
            "report": report_result.get("report", {})
        }