class PromptTemplates:
    @staticmethod
    def get_system_message():
        """
        LLM 시스템 메시지 템플릿을 반환합니다.
        """
        return """
        당신은 웹 분석 및 UX/UI 개선 전문가 AI 어시스턴트입니다. 당신은 사용자의 웹사이트에서 고객 경험을 향상시키기 위한 분석과 개선 제안을 제공합니다.

        당신은 다음 도구를 사용할 수 있습니다:

        1. BigQuery 도구:
           - run_bigquery: SQL 쿼리를 실행하여 GA 데이터를 분석합니다.
           - explore_bigquery_dataset: 사용 가능한 데이터셋과 테이블을 탐색합니다.
           - get_bigquery_suggestions: 사용자 의도에 맞는 쿼리 제안을 생성합니다.

        2. 웹 자동화 도구:
           - execute_web_journey: 웹사이트 사용자 여정을 자동화하여 실행합니다.
           - analyze_web_journey: 실행된 여정을 분석하고 UX/UI 개선 인사이트를 생성합니다.

        사용자가 분석, 시나리오 작성, 웹사이트 테스트, 개선 제안 등을 요청할 때 적절한 도구를 사용하세요.

        [실행 순서 가이드]
        1. 분석 요청 시: 먼저 dataset 탐색 → 쿼리 제안 → 쿼리 실행 순으로 진행하세요.
        2. 웹사이트 테스트 시: 시나리오 작성 → 여정 실행 → 여정 분석 → 개선 제안 순으로 진행하세요.
        3. 여러 데이터 소스를 통합하여 인사이트를 도출하세요.

        사용자의 질문에 직접적으로 답하고, 필요한 경우 추가 정보를 요청하세요.
        """
    
    @staticmethod
    def get_journey_template(url: str, credentials = None):
        """
        기본적인 웹 여정 템플릿을 반환합니다.
        
        Args:
            url (str): 탐색할 URL
            credentials (dict, optional): 로그인 자격 증명
            
        Returns:
            list: 여정 시나리오 템플릿
        """
        template = [
            {
                "action": "navigate",
                "url": url,
                "critical": True
            },
            {
                "action": "wait",
                "seconds": 3
            }
        ]
        
        # 로그인 자격 증명이 제공된 경우 로그인 단계 추가
        if credentials and "username" in credentials and "password" in credentials:
            template.extend([
                {
                    "action": "login",
                    "url": f"{url}/login",
                    "username": credentials["username"],
                    "password": credentials["password"],
                    "username_selector": credentials.get("username_selector", "#email"),
                    "password_selector": credentials.get("password_selector", "#password"),
                    "submit_selector": credentials.get("submit_selector", "button[type='submit']"),
                    "cookie_selector": credentials.get("cookie_selector"),
                    "critical": True
                },
                {
                    "action": "wait",
                    "seconds": 3
                }
            ])
        
        # 페이지 분석 단계 추가
        template.extend([
            {
                "action": "take_screenshot"
            },
            {
                "action": "analyze_page"
            }
        ])
        
        return template