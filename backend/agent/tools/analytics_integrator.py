import os
import json
import pandas as pd
import datetime
from typing import Dict, List, Any, Optional
from google.cloud import bigquery

class AnalyticsIntegrator:
    def __init__(self, project_id: str, credentials_path: Optional[str] = None):
        """
        BigQuery와 웹 자동화 데이터를 통합하는 클래스 초기화
        
        Args:
            project_id (str): GCP 프로젝트 ID
            credentials_path (str, optional): GCP 서비스 계정 키 파일 경로
        """
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
    
    async def query_analytics_data(self, query: str) -> Dict[str, Any]:
        """
        BigQuery에서 분석 데이터를 쿼리합니다.
        
        Args:
            query (str): 실행할 SQL 쿼리
            
        Returns:
            Dict: 쿼리 결과
        """
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            # 결과를 DataFrame으로 변환
            df = results.to_dataframe()
            
            # DataFrame을 리스트로 변환
            records = df.to_dict('records')
            
            return {
                "success": True,
                "message": "쿼리 성공",
                "row_count": len(records),
                "data": records
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"쿼리 실행 오류: {str(e)}"
            }
    
    async def compare_user_journey_with_analytics(
        self, 
        journey_data: Dict[str, Any], 
        page_path: str, 
        date_range: int = 30
    ) -> Dict[str, Any]:
        """
        웹 자동화로 수집한 사용자 여정 데이터와 GA 분석 데이터를 비교합니다.
        
        Args:
            journey_data (Dict): 자동화 도구로 수집한 사용자 여정 데이터
            page_path (str): 분석할 페이지 경로
            date_range (int): 분석할 일수 (기본값: 30일)
            
        Returns:
            Dict: 비교 분석 결과
        """
        # 날짜 범위 계산
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=date_range)).strftime('%Y-%m-%d')
        
        # GA 데이터 쿼리
        ga_query = f"""
        SELECT
          page_path,
          COUNT(DISTINCT session_id) AS sessions,
          COUNT(DISTINCT user_pseudo_id) AS users,
          AVG(engagement_time_msec) / 1000 AS avg_time_seconds,
          COUNT(event_name) AS events
        FROM
          `{self.project_id}.analytics_data.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date.replace('-', '')}' AND '{end_date.replace('-', '')}'
          AND page_path LIKE '{page_path}%'
        GROUP BY
          page_path
        ORDER BY
          sessions DESC
        LIMIT 100
        """
        
        ga_results = await self.query_analytics_data(ga_query)
        
        if not ga_results.get("success", False):
            return {
                "success": False,
                "message": f"GA 데이터 조회 실패: {ga_results.get('message')}"
            }
        
        # 페이지별 평균 체류 시간 쿼리
        time_query = f"""
        SELECT
          page_path,
          AVG(engagement_time_msec) / 1000 AS avg_time_seconds
        FROM
          `{self.project_id}.analytics_data.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date.replace('-', '')}' AND '{end_date.replace('-', '')}'
          AND page_path LIKE '{page_path}%'
        GROUP BY
          page_path
        ORDER BY
          avg_time_seconds DESC
        LIMIT 100
        """
        
        time_results = await self.query_analytics_data(time_query)
        
        # 페이지별 이탈률 쿼리
        bounce_query = f"""
        SELECT
          entrance_page_path AS page_path,
          COUNTIF(is_exit = TRUE) / COUNT(*) AS bounce_rate
        FROM
          `{self.project_id}.analytics_data.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date.replace('-', '')}' AND '{end_date.replace('-', '')}'
          AND entrance_page_path LIKE '{page_path}%'
        GROUP BY
          entrance_page_path
        ORDER BY
          bounce_rate DESC
        LIMIT 100
        """
        
        bounce_results = await self.query_analytics_data(bounce_query)
        
        # 자동화 데이터와 GA 데이터 비교
        comparison = {
            "page_path": page_path,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
                "days": date_range
            },
            "analytics": {
                "ga_data": ga_results.get("data", []),
                "time_data": time_results.get("data", []),
                "bounce_data": bounce_results.get("data", [])
            },
            "automation": {
                "journey_steps": journey_data.get("steps", []),
                "journey_duration_seconds": journey_data.get("duration", 0),
                "errors_encountered": journey_data.get("errors", []),
                "ui_metrics": journey_data.get("ui_metrics", {})
            },
            "insights": []
        }
        
        # 인사이트 도출
        if ga_results.get("success", False) and "data" in ga_results:
            ga_data = ga_results["data"]
            
            # 1. 평균 체류 시간 비교
            if time_results.get("success", False) and "data" in time_results and time_results["data"]:
                avg_time = time_results["data"][0].get("avg_time_seconds", 0)
                journey_time = journey_data.get("duration", 0)
                
                if journey_time > avg_time * 1.5:
                    comparison["insights"].append({
                        "type": "time_insight",
                        "severity": "high",
                        "title": "자동화 여정이 평균보다 훨씬 오래 걸림",
                        "description": f"자동화 여정 시간({journey_time:.2f}초)이 실제 사용자 평균({avg_time:.2f}초)보다 {((journey_time/avg_time)-1)*100:.2f}% 더 깁니다. 사용자 경험 개선이 필요합니다."
                    })
                elif journey_time < avg_time * 0.5:
                    comparison["insights"].append({
                        "type": "time_insight",
                        "severity": "medium",
                        "title": "자동화 여정이 평균보다 훨씬 짧음",
                        "description": f"자동화 여정 시간({journey_time:.2f}초)이 실제 사용자 평균({avg_time:.2f}초)보다 {(1-(journey_time/avg_time))*100:.2f}% 더 짧습니다. 이는 자동화 스크립트가 실제 사용자 행동을 완전히 모방하지 못함을 나타냅니다."
                    })
            
            # 2. 이탈률 관련 인사이트
            if bounce_results.get("success", False) and "data" in bounce_results and bounce_results["data"]:
                bounce_rate = bounce_results["data"][0].get("bounce_rate", 0)
                
                if bounce_rate > 0.5:  # 50% 이상 이탈률
                    comparison["insights"].append({
                        "type": "bounce_insight",
                        "severity": "high",
                        "title": "높은 이탈률 문제",
                        "description": f"현재 페이지의 이탈률이 {bounce_rate*100:.2f}%로 매우 높습니다. 자동화 테스트 중 발견된 UI 문제가 사용자 이탈의 원인일 수 있습니다."
                    })
        
        # 3. UI 메트릭 기반 인사이트
        ui_metrics = journey_data.get("ui_metrics", {})
        if ui_metrics:
            # 페이지 로드 시간 분석
            if "performance" in ui_metrics and ui_metrics["performance"]:
                load_time_ms = ui_metrics["performance"].get("loadTimeMs", 0)
                
                if load_time_ms > 3000:  # 3초 이상 로드 시간
                    comparison["insights"].append({
                        "type": "performance_insight",
                        "severity": "high",
                        "title": "느린 페이지 로드 시간",
                        "description": f"페이지 로드 시간이 {load_time_ms/1000:.2f}초로 권장치(3초)보다 깁니다. 이것이 높은 이탈률({bounce_results['data'][0].get('bounce_rate', 0)*100:.2f}%)의 원인일 수 있습니다."
                    })
            
            # 클릭 가능한 요소 문제 분석
            if "clickableMetrics" in ui_metrics:
                small_targets_ratio = ui_metrics["clickableMetrics"].get("smallTargets", 0) / max(ui_metrics["clickableMetrics"].get("total", 1), 1)
                
                if small_targets_ratio > 0.3:  # 30% 이상의 요소가 작은 경우
                    comparison["insights"].append({
                        "type": "usability_insight",
                        "severity": "medium",
                        "title": "작은 클릭 영역 문제",
                        "description": f"클릭 가능한 요소의 {small_targets_ratio*100:.2f}%가 권장 크기(44x44px)보다 작습니다. 이는 모바일 사용자 경험을 저하시킬 수 있습니다."
                    })
        
        return {
            "success": True,
            "message": "사용자 여정과 GA 데이터 비교 성공",
            "comparison": comparison
        }
    
    async def generate_ux_improvement_report(
        self, 
        journey_data: Dict[str, Any],
        analytics_comparison: Dict[str, Any],
        a11y_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        UX 개선 보고서를 생성합니다.
        
        Args:
            journey_data (Dict): 자동화 도구로 수집한 사용자 여정 데이터
            analytics_comparison (Dict): GA 데이터 비교 분석 결과
            a11y_results (Dict): 접근성 감사 결과
            
        Returns:
            Dict: UX 개선 보고서
        """
        # 보고서 기본 구조
        report = {
            "title": f"UX/UI 개선 보고서 - {datetime.datetime.now().strftime('%Y-%m-%d')}",
            "summary": {
                "issues_found": 0,
                "critical_issues": 0,
                "high_priority_issues": 0,
                "medium_priority_issues": 0,
                "low_priority_issues": 0
            },
            "journey_analysis": {
                "path": journey_data.get("path", "N/A"),
                "duration_seconds": journey_data.get("duration", 0),
                "steps_count": len(journey_data.get("steps", [])),
                "errors_count": len(journey_data.get("errors", []))
            },
            "issues": [],
            "recommendations": []
        }
        
        # 1. 인사이트에서 이슈 추출
        insights = analytics_comparison.get("comparison", {}).get("insights", [])
        for insight in insights:
            severity = insight.get("severity", "medium")
            severity_value = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity, 2)
            
            report["issues"].append({
                "title": insight.get("title", "이슈"),
                "description": insight.get("description", ""),
                "severity": severity,
                "severity_value": severity_value,
                "type": insight.get("type", "general"),
                "source": "analytics_comparison",
                "evidence": "GA 데이터 분석"
            })
            
            # 이슈 카운트 업데이트
            report["summary"]["issues_found"] += 1
            if severity == "critical":
                report["summary"]["critical_issues"] += 1
            elif severity == "high":
                report["summary"]["high_priority_issues"] += 1
            elif severity == "medium":
                report["summary"]["medium_priority_issues"] += 1
            elif severity == "low":
                report["summary"]["low_priority_issues"] += 1
        
        # 2. 접근성 이슈 추출
        a11y_violations = a11y_results.get("results", {}).get("mainViolations", [])
        for violation in a11y_violations:
            impact = violation.get("impact", "minor")
            severity = {"critical": "critical", "serious": "high", "moderate": "medium", "minor": "low"}.get(impact, "medium")
            severity_value = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity, 2)
            
            report["issues"].append({
                "title": f"접근성 문제: {violation.get('id', '알 수 없음')}",
                "description": violation.get("description", "") + " - " + violation.get("help", ""),
                "severity": severity,
                "severity_value": severity_value,
                "type": "accessibility",
                "source": "a11y_audit",
                "evidence": f"영향 받는 요소 수: {violation.get('nodes', 0)}개",
                "helpUrl": violation.get("helpUrl", "")
            })
            
            # 이슈 카운트 업데이트
            report["summary"]["issues_found"] += 1
            if severity == "critical":
                report["summary"]["critical_issues"] += 1
            elif severity == "high":
                report["summary"]["high_priority_issues"] += 1
            elif severity == "medium":
                report["summary"]["medium_priority_issues"] += 1
            elif severity == "low":
                report["summary"]["low_priority_issues"] += 1
        
        # 3. 사용자 여정 오류 추출
        journey_errors = journey_data.get("errors", [])
        for error in journey_errors:
            report["issues"].append({
                "title": f"사용자 여정 오류: {error.get('step', '알 수 없는 단계')}",
                "description": error.get("message", "오류 발생"),
                "severity": "high",
                "severity_value": 3,
                "type": "journey_error",
                "source": "automation",
                "evidence": f"단계: {error.get('step_index', '?')}, 요소: {error.get('element', 'N/A')}"
            })
            
            # 이슈 카운트 업데이트
            report["summary"]["issues_found"] += 1
            report["summary"]["high_priority_issues"] += 1
        
        # 4. UI 메트릭 기반 이슈 추출
        ui_metrics = journey_data.get("ui_metrics", {})
        
        # 4.1. 로딩 성능 이슈
        if ui_metrics.get("performance", {}).get("loadTimeMs", 0) > 3000:
            report["issues"].append({
                "title": "느린 페이지 로드 시간",
                "description": f"페이지 로드 시간이 {ui_metrics['performance']['loadTimeMs']/1000:.2f}초로 권장치(3초)보다 깁니다.",
                "severity": "high",
                "severity_value": 3,
                "type": "performance",
                "source": "ui_metrics",
                "evidence": f"로드 시간: {ui_metrics['performance']['loadTimeMs']/1000:.2f}초"
            })
            
            # 이슈 카운트 업데이트
            report["summary"]["issues_found"] += 1
            report["summary"]["high_priority_issues"] += 1
        
        # 4.2. 작은 클릭 영역 이슈
        if "clickableMetrics" in ui_metrics:
            small_targets = ui_metrics["clickableMetrics"].get("smallTargets", 0)
            total_targets = ui_metrics["clickableMetrics"].get("total", 1)
            small_targets_ratio = small_targets / max(total_targets, 1)
            
            if small_targets_ratio > 0.3:  # 30% 이상의 요소가 작은 경우
                report["issues"].append({
                    "title": "작은 클릭 영역 문제",
                    "description": f"클릭 가능한 요소 중 {small_targets}개({small_targets_ratio*100:.2f}%)가 권장 크기(44x44px)보다 작습니다.",
                    "severity": "medium",
                    "severity_value": 2,
                    "type": "usability",
                    "source": "ui_metrics",
                    "evidence": f"작은 클릭 영역: {small_targets}개 / 전체: {total_targets}개"
                })
                
                # 이슈 카운트 업데이트
                report["summary"]["issues_found"] += 1
                report["summary"]["medium_priority_issues"] += 1
        
        # 4.3. 라벨 없는 클릭 요소 이슈
        if "clickableMetrics" in ui_metrics:
            no_labels = ui_metrics["clickableMetrics"].get("withoutLabels", 0)
            total_targets = ui_metrics["clickableMetrics"].get("total", 1)
            no_labels_ratio = no_labels / max(total_targets, 1)
            
            if no_labels_ratio > 0.1:  # 10% 이상의 요소에 라벨이 없는 경우
                report["issues"].append({
                    "title": "라벨 없는 클릭 요소 문제",
                    "description": f"클릭 가능한 요소 중 {no_labels}개({no_labels_ratio*100:.2f}%)에 적절한 라벨이 없습니다.",
                    "severity": "medium",
                    "severity_value": 2,
                    "type": "accessibility",
                    "source": "ui_metrics",
                    "evidence": f"라벨 없는 요소: {no_labels}개 / 전체: {total_targets}개"
                })
                
                # 이슈 카운트 업데이트
                report["summary"]["issues_found"] += 1
                report["summary"]["medium_priority_issues"] += 1
        
        # 4.4 이미지 대체 텍스트 이슈
        if "imageMetrics" in ui_metrics:
            without_alt = ui_metrics["imageMetrics"].get("withoutAlt", 0)
            total_images = ui_metrics["imageMetrics"].get("total", 1)
            without_alt_ratio = without_alt / max(total_images, 1)
            
            if without_alt_ratio > 0.2:  # 20% 이상의 이미지에 대체 텍스트가 없는 경우
                report["issues"].append({
                    "title": "대체 텍스트 없는 이미지 문제",
                    "description": f"이미지 중 {without_alt}개({without_alt_ratio*100:.2f}%)에 대체 텍스트(alt)가 없습니다.",
                    "severity": "medium",
                    "severity_value": 2,
                    "type": "accessibility",
                    "source": "ui_metrics",
                    "evidence": f"대체 텍스트 없는 이미지: {without_alt}개 / 전체: {total_images}개"
                })
                
                # 이슈 카운트 업데이트
                report["summary"]["issues_found"] += 1
                report["summary"]["medium_priority_issues"] += 1
        
        # 5. 권장 사항 생성
        # 이슈를 심각도에 따라 정렬
        sorted_issues = sorted(report["issues"], key=lambda x: x["severity_value"], reverse=True)
        
        # 상위 5개 이슈에 대한 권장 사항 생성
        for i, issue in enumerate(sorted_issues[:5]):
            issue_type = issue.get("type", "general")
            
            if issue_type == "performance":
                report["recommendations"].append({
                    "priority": i + 1,
                    "title": f"성능 최적화: {issue['title']}",
                    "description": "페이지 로드 시간을 개선하기 위해 이미지 최적화, 자바스크립트 최소화, 중요하지 않은 리소스 지연 로딩 등의 기법을 적용하세요.",
                    "related_issue": issue["title"],
                    "potential_impact": "높음"
                })
            elif issue_type == "accessibility":
                report["recommendations"].append({
                    "priority": i + 1,
                    "title": f"접근성 개선: {issue['title']}",
                    "description": f"WCAG 지침에 따라 해당 접근성 문제를 수정하세요. 관련 도움말: {issue.get('helpUrl', '해당 없음')}",
                    "related_issue": issue["title"],
                    "potential_impact": "높음"
                })
            elif issue_type == "usability":
                report["recommendations"].append({
                    "priority": i + 1,
                    "title": f"사용성 개선: {issue['title']}",
                    "description": "모든 대화형 요소가 충분한 크기와 적절한 간격을 가지도록 개선하세요. 특히 모바일 사용자를 위한 최소 44x44 픽셀 크기를 권장합니다.",
                    "related_issue": issue["title"],
                    "potential_impact": "중간"
                })
            elif issue_type == "journey_error":
                report["recommendations"].append({
                    "priority": i + 1,
                    "title": f"사용자 여정 개선: {issue['title']}",
                    "description": "사용자가 목표를 달성하는 과정에서 발생한 오류를 수정하세요. 명확한 오류 메시지와 복구 경로를 제공하는 것이 중요합니다.",
                    "related_issue": issue["title"],
                    "potential_impact": "높음"
                })
            else:
                report["recommendations"].append({
                    "priority": i + 1,
                    "title": f"일반 개선: {issue['title']}",
                    "description": "이 문제를 해결하여 전반적인 사용자 경험을 개선하세요.",
                    "related_issue": issue["title"],
                    "potential_impact": "중간"
                })
        
        return {
            "success": True,
            "message": "UX 개선 보고서 생성 성공",
            "report": report
        }
