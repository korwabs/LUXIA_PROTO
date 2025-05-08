#!/usr/bin/env python3
"""
LG 브라질 사이트 CAPTCHA 우회 로그인 예제 스크립트

이 스크립트는 LG 브라질 웹사이트에 CAPTCHA 우회 기능을 사용하여
로그인하고 마이페이지에 접근하는 과정을 자동화합니다.
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools import SandboxBrowserCaptchaBypass
from agentpress.thread_manager import ThreadManager
from services.supabase import DBConnection
from utils.logger import logger

# 환경 변수 로드
load_dotenv()

async def main():
    """메인 실행 함수"""
    
    # 데이터베이스 연결 설정
    db = DBConnection()
    await db.initialize()
    
    # 쓰레드 매니저 설정
    thread_manager = ThreadManager(db=db)
    
    # 스크립트 실행을 위한 임의의 프로젝트 ID 및 쓰레드 ID
    # 실제 운영 환경에서는 이 값들이 데이터베이스에서 가져온 실제 ID여야 합니다.
    project_id = "example_project_id"
    thread_id = "example_thread_id"
    
    try:
        # SandboxBrowserCaptchaBypass 도구 인스턴스 생성
        browser_tool = SandboxBrowserCaptchaBypass(
            project_id=project_id,
            thread_id=thread_id,
            thread_manager=thread_manager,
            is_headless=False  # CAPTCHA 우회를 위해 비헤드리스 모드 사용
        )
        
        # 1. 브라우저 설정
        logger.info("브라우저 설정 중...")
        setup_result = await browser_tool._setup_browser_config()
        if not setup_result.get("success", False):
            logger.error(f"브라우저 설정 실패: {setup_result}")
            return
        
        # 2. LG 브라질 로그인 페이지로 이동
        login_url = "https://www.lge.com/br/login"
        username = "sadforest@naver.com"
        password = "juni!#18"
        domain = "lge.com"
        
        logger.info(f"LG 브라질 로그인 시도: {login_url}")
        login_result = await browser_tool.browser_login_with_captcha_bypass(
            url=login_url,
            username=username,
            password=password,
            domain=domain,
            use_cookie_bypass=True,
            use_non_headless=True,
            use_human_input=True
        )
        
        # 3. 로그인 결과 확인
        if login_result.get("success", False):
            logger.info(f"로그인 성공: {login_result.get('message')}")
            
            # 4. CAPTCHA 감지 확인
            if login_result.get("data", {}).get("captcha_detected", False):
                logger.warning(f"CAPTCHA 감지됨: {login_result.get('data', {}).get('note')}")
                
                # CAPTCHA 스크린샷 확인
                screenshot_path = login_result.get("data", {}).get("screenshot_path")
                if screenshot_path:
                    logger.info(f"CAPTCHA 스크린샷 저장됨: {screenshot_path}")
                
                # 수동 개입 필요
                logger.info("수동 개입이 필요합니다. 스크립트를 중단합니다.")
                return
            
            # 5. 마이페이지로 이동
            logger.info("마이페이지로 이동 시도...")
            await browser_tool.browser_wait(3)  # 로그인 후 잠시 대기
            
            mypage_result = await browser_tool.browser_navigate_to_mypage(
                mypage_text="Minha conta"  # 포르투갈어로 "내 계정"
            )
            
            if mypage_result.get("success", False):
                logger.info(f"마이페이지 이동 성공: {mypage_result.get('data', {}).get('url')}")
                
                # 6. 페이지 구조 분석
                logger.info("페이지 구조 분석 중...")
                structure_result = await browser_tool.browser_analyze_page_structure()
                
                if structure_result.get("success", False):
                    # 분석 결과 저장
                    structure_data = structure_result.get("data", {}).get("structure", {})
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    result_file = f"/workspace/analysis_results_{timestamp}.json"
                    
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(structure_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"페이지 구조 분석 결과 저장됨: {result_file}")
                    
                    # 7. UI 지표 추출
                    logger.info("UI 지표 추출 중...")
                    metrics_result = await browser_tool.browser_extract_ui_metrics()
                    
                    if metrics_result.get("success", False):
                        # 지표 결과 저장
                        metrics_data = metrics_result.get("data", {}).get("metrics", {})
                        metrics_file = f"/workspace/ui_metrics_{timestamp}.json"
                        
                        with open(metrics_file, "w", encoding="utf-8") as f:
                            json.dump(metrics_data, f, indent=2, ensure_ascii=False)
                        
                        logger.info(f"UI 지표 결과 저장됨: {metrics_file}")
                    else:
                        logger.error(f"UI 지표 추출 실패: {metrics_result}")
                else:
                    logger.error(f"페이지 구조 분석 실패: {structure_result}")
            else:
                logger.error(f"마이페이지 이동 실패: {mypage_result}")
        else:
            logger.error(f"로그인 실패: {login_result}")
    
    except Exception as e:
        logger.error(f"스크립트 실행 중 오류 발생: {str(e)}")
    
    finally:
        # 리소스 정리
        await db.disconnect()
        logger.info("스크립트 실행 완료")

if __name__ == "__main__":
    asyncio.run(main())
