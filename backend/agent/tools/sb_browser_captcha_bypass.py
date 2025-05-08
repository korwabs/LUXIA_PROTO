import os
import json
import base64
import traceback
from datetime import datetime

from agentpress.tool import ToolResult, openapi_schema, xml_schema
from agentpress.thread_manager import ThreadManager
from sandbox.sandbox import SandboxToolsBase, Sandbox
from utils.logger import logger
from agent.tools.sb_browser_tool import SandboxBrowserTool

class SandboxBrowserCaptchaBypass(SandboxBrowserTool):
    """
    CAPTCHA 우회를 위한 확장 브라우저 도구입니다.
    비헤드리스 모드, 쿠키 관리, 지연된 동작 시뮬레이션 등의 기능을 제공합니다.
    """
    
    def __init__(self, project_id: str, thread_id: str, thread_manager: ThreadManager, 
                 is_headless: bool = False, user_agent: str = None):
        super().__init__(project_id, thread_id, thread_manager)
        self.is_headless = is_headless
        self.user_agent = user_agent
        self.cookies_dir = '/workspace/browser_cookies'
        self.screenshots_dir = '/workspace/screenshots'
    
    async def _setup_browser_config(self):
        """
        브라우저 초기 설정을 구성합니다.
        """
        try:
            await self._ensure_sandbox()
            
            # 디렉토리 생성
            os.makedirs(self.cookies_dir, exist_ok=True)
            os.makedirs(self.screenshots_dir, exist_ok=True)
            
            # 브라우저 설정 구성
            config = {
                "headless": self.is_headless
            }
            
            if self.user_agent:
                config["userAgent"] = self.user_agent
            else:
                # 일반적인 데스크탑 브라우저 UA 설정
                config["userAgent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            
            # 브라우저 설정 적용
            result = await self._execute_browser_action("set_browser_config", config)
            return result
        except Exception as e:
            logger.error(f"브라우저 설정 오류: {str(e)}")
            return self.fail_response(f"브라우저 설정 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_set_non_headless",
            "description": "브라우저를 비헤드리스 모드로 설정합니다. CAPTCHA 우회에 효과적입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_agent": {
                        "type": "string",
                        "description": "사용자 에이전트 설정 (기본값: 일반 Chrome 사용자 에이전트)"
                    }
                }
            }
        }
    })
    @xml_schema(
        tag_name="browser-set-non-headless",
        mappings=[
            {"param_name": "user_agent", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-set-non-headless>
        Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36
        </browser-set-non-headless>
        '''
    )
    async def browser_set_non_headless(self, user_agent: str = None) -> ToolResult:
        """
        브라우저를 비헤드리스 모드로 설정합니다. CAPTCHA 우회에 효과적입니다.
        
        Args:
            user_agent (str, optional): 사용자 에이전트 설정 (기본값: 일반 Chrome 사용자 에이전트)
            
        Returns:
            ToolResult: 설정 결과
        """
        self.is_headless = False
        if user_agent:
            self.user_agent = user_agent
        
        result = await self._setup_browser_config()
        if result.get("success", False):
            return self.success_response({"message": "브라우저가 비헤드리스 모드로 설정되었습니다."})
        return result

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_save_cookies",
            "description": "현재 페이지의 쿠키를 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "쿠키 도메인 (예: example.com)"
                    },
                    "filename": {
                        "type": "string",
                        "description": "저장할 파일명 (기본값: domain_cookies.json)"
                    }
                },
                "required": ["domain"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-save-cookies",
        mappings=[
            {"param_name": "domain", "node_type": "attribute", "path": "."},
            {"param_name": "filename", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-save-cookies domain="example.com">
        example_cookies.json
        </browser-save-cookies>
        '''
    )
    async def browser_save_cookies(self, domain: str, filename: str = None) -> ToolResult:
        """
        현재 페이지의 쿠키를 저장합니다.
        
        Args:
            domain (str): 쿠키 도메인 (예: example.com)
            filename (str, optional): 저장할 파일명 (기본값: domain_cookies.json)
            
        Returns:
            ToolResult: 저장 결과
        """
        try:
            await self._ensure_sandbox()
            
            if not filename:
                filename = f"{domain.replace('.', '_')}_cookies.json"
            
            filepath = os.path.join(self.cookies_dir, filename)
            
            # 쿠키 가져오기
            cookies_result = await self._execute_browser_action("get_cookies", {"domain": domain})
            
            if not cookies_result.get("success", False):
                return self.fail_response(f"쿠키 가져오기 실패: {cookies_result.get('message', '')}")
            
            cookies = cookies_result.get("data", {}).get("cookies", [])
            
            # 쿠키 파일 저장
            with open(filepath, 'w') as f:
                json.dump(cookies, f)
            
            return self.success_response({
                "message": f"쿠키가 성공적으로 저장되었습니다.",
                "filepath": filepath,
                "cookie_count": len(cookies)
            })
            
        except Exception as e:
            logger.error(f"쿠키 저장 오류: {str(e)}")
            return self.fail_response(f"쿠키 저장 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_load_cookies",
            "description": "저장된 쿠키를 브라우저에 로드합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "쿠키 파일 경로"
                    }
                },
                "required": ["filepath"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-load-cookies",
        mappings=[
            {"param_name": "filepath", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-load-cookies>
        /workspace/browser_cookies/example_com_cookies.json
        </browser-load-cookies>
        '''
    )
    async def browser_load_cookies(self, filepath: str) -> ToolResult:
        """
        저장된 쿠키를 브라우저에 로드합니다.
        
        Args:
            filepath (str): 쿠키 파일 경로
            
        Returns:
            ToolResult: 로드 결과
        """
        try:
            await self._ensure_sandbox()
            
            if not os.path.exists(filepath):
                return self.fail_response(f"쿠키 파일을 찾을 수 없습니다: {filepath}")
            
            # 쿠키 파일 로드
            with open(filepath, 'r') as f:
                cookies = json.load(f)
            
            # 쿠키 설정
            result = await self._execute_browser_action("set_cookies", {"cookies": cookies})
            
            if not result.get("success", False):
                return self.fail_response(f"쿠키 설정 실패: {result.get('message', '')}")
            
            return self.success_response({
                "message": f"쿠키가 성공적으로 로드되었습니다.",
                "cookie_count": len(cookies)
            })
            
        except Exception as e:
            logger.error(f"쿠키 로드 오류: {str(e)}")
            return self.fail_response(f"쿠키 로드 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_set_cookie",
            "description": "브라우저에 쿠키를 설정합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "쿠키 이름"
                    },
                    "value": {
                        "type": "string", 
                        "description": "쿠키 값"
                    },
                    "domain": {
                        "type": "string",
                        "description": "쿠키 도메인 (예: .example.com)"
                    },
                    "path": {
                        "type": "string",
                        "description": "쿠키 경로 (기본값: /)"
                    },
                    "secure": {
                        "type": "boolean",
                        "description": "보안 쿠키 여부 (기본값: true)"
                    }
                },
                "required": ["name", "value", "domain"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-set-cookie",
        mappings=[
            {"param_name": "name", "node_type": "attribute", "path": "."},
            {"param_name": "value", "node_type": "attribute", "path": "."},
            {"param_name": "domain", "node_type": "attribute", "path": "."},
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "secure", "node_type": "attribute", "path": "."}
        ],
        example='''
        <browser-set-cookie name="session" value="abc123" domain=".example.com" path="/" secure="true"></browser-set-cookie>
        '''
    )
    async def browser_set_cookie(self, name: str, value: str, domain: str, 
                               path: str = "/", secure: bool = True) -> ToolResult:
        """
        브라우저에 쿠키를 설정합니다.
        
        Args:
            name (str): 쿠키 이름
            value (str): 쿠키 값
            domain (str): 쿠키 도메인 (예: .example.com)
            path (str, optional): 쿠키 경로 (기본값: /)
            secure (bool, optional): 보안 쿠키 여부 (기본값: true)
            
        Returns:
            ToolResult: 설정 결과
        """
        try:
            await self._ensure_sandbox()
            
            cookie = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "secure": secure
            }
            
            result = await self._execute_browser_action("set_cookies", {"cookies": [cookie]})
            
            if not result.get("success", False):
                return self.fail_response(f"쿠키 설정 실패: {result.get('message', '')}")
            
            return self.success_response({
                "message": f"쿠키 '{name}'이(가) 성공적으로 설정되었습니다."
            })
            
        except Exception as e:
            logger.error(f"쿠키 설정 오류: {str(e)}")
            return self.fail_response(f"쿠키 설정 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_human_like_input",
            "description": "인간과 유사한 속도로 텍스트를 입력합니다. CAPTCHA 우회에 도움이 됩니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "입력할 요소의 인덱스"
                    },
                    "text": {
                        "type": "string",
                        "description": "입력할 텍스트"
                    },
                    "delay_min": {
                        "type": "integer",
                        "description": "최소 타이핑 지연 시간(ms) (기본값: 50)"
                    },
                    "delay_max": {
                        "type": "integer",
                        "description": "최대 타이핑 지연 시간(ms) (기본값: 150)"
                    }
                },
                "required": ["index", "text"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-human-like-input",
        mappings=[
            {"param_name": "index", "node_type": "attribute", "path": "."},
            {"param_name": "text", "node_type": "content", "path": "."},
            {"param_name": "delay_min", "node_type": "attribute", "path": "."},
            {"param_name": "delay_max", "node_type": "attribute", "path": "."}
        ],
        example='''
        <browser-human-like-input index="2" delay_min="70" delay_max="200">
        Hello, I am a human typing this text.
        </browser-human-like-input>
        '''
    )
    async def browser_human_like_input(self, index: int, text: str, 
                                    delay_min: int = 50, delay_max: int = 150) -> ToolResult:
        """
        인간과 유사한 속도로 텍스트를 입력합니다. CAPTCHA 우회에 도움이 됩니다.
        
        Args:
            index (int): 입력할 요소의 인덱스
            text (str): 입력할 텍스트
            delay_min (int, optional): 최소 타이핑 지연 시간(ms) (기본값: 50)
            delay_max (int, optional): 최대 타이핑 지연 시간(ms) (기본값: 150)
            
        Returns:
            ToolResult: 입력 결과
        """
        try:
            await self._ensure_sandbox()
            
            result = await self._execute_browser_action("human_like_input", {
                "index": index,
                "text": text,
                "delay_min": delay_min,
                "delay_max": delay_max
            })
            
            if not result.get("success", False):
                return self.fail_response(f"인간형 입력 실패: {result.get('message', '')}")
            
            return self.success_response({
                "message": f"인간과 유사한 방식으로 텍스트를 성공적으로 입력했습니다."
            })
            
        except Exception as e:
            logger.error(f"인간형 입력 오류: {str(e)}")
            return self.fail_response(f"인간형 입력 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_take_captcha_screenshot",
            "description": "CAPTCHA 영역의 스크린샷을 촬영합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "CAPTCHA 요소의 인덱스"
                    },
                    "filename": {
                        "type": "string",
                        "description": "저장할 파일명 (기본값: captcha_날짜시간.png)"
                    }
                },
                "required": ["index"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-take-captcha-screenshot",
        mappings=[
            {"param_name": "index", "node_type": "attribute", "path": "."},
            {"param_name": "filename", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-take-captcha-screenshot index="5">
        captcha_image.png
        </browser-take-captcha-screenshot>
        '''
    )
    async def browser_take_captcha_screenshot(self, index: int, filename: str = None) -> ToolResult:
        """
        CAPTCHA 영역의 스크린샷을 촬영합니다.
        
        Args:
            index (int): CAPTCHA 요소의 인덱스
            filename (str, optional): 저장할 파일명 (기본값: captcha_날짜시간.png)
            
        Returns:
            ToolResult: 스크린샷 결과
        """
        try:
            await self._ensure_sandbox()
            
            if not filename:
                filename = f"captcha_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            filepath = os.path.join(self.screenshots_dir, filename)
            
            result = await self._execute_browser_action("take_element_screenshot", {
                "index": index,
                "path": filepath
            })
            
            if not result.get("success", False):
                return self.fail_response(f"CAPTCHA 스크린샷 촬영 실패: {result.get('message', '')}")
            
            return self.success_response({
                "message": "CAPTCHA 스크린샷이 성공적으로 저장되었습니다.",
                "filepath": filepath
            })
            
        except Exception as e:
            logger.error(f"CAPTCHA 스크린샷 오류: {str(e)}")
            return self.fail_response(f"CAPTCHA 스크린샷 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_ocr_element",
            "description": "요소의 텍스트를 OCR로 인식합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "OCR로 인식할 요소의 인덱스"
                    }
                },
                "required": ["index"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-ocr-element",
        mappings=[
            {"param_name": "index", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-ocr-element>
        5
        </browser-ocr-element>
        '''
    )
    async def browser_ocr_element(self, index: int) -> ToolResult:
        """
        요소의 텍스트를 OCR로 인식합니다.
        
        Args:
            index (int): OCR로 인식할 요소의 인덱스
            
        Returns:
            ToolResult: OCR 결과
        """
        try:
            await self._ensure_sandbox()
            
            result = await self._execute_browser_action("ocr_element", {"index": index})
            
            if not result.get("success", False):
                return self.fail_response(f"OCR 인식 실패: {result.get('message', '')}")
            
            ocr_text = result.get("data", {}).get("text", "")
            
            return self.success_response({
                "message": "OCR 인식 성공",
                "text": ocr_text
            })
            
        except Exception as e:
            logger.error(f"OCR 인식 오류: {str(e)}")
            return self.fail_response(f"OCR 인식 오류: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_login_with_captcha_bypass",
            "description": "CAPTCHA 우회 기능을 사용하여 웹사이트에 로그인합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "로그인 페이지 URL"
                    },
                    "username": {
                        "type": "string",
                        "description": "사용자명/이메일"
                    },
                    "password": {
                        "type": "string",
                        "description": "비밀번호"
                    },
                    "use_cookie_bypass": {
                        "type": "boolean",
                        "description": "쿠키를 이용한 우회 시도 여부 (기본값: true)"
                    },
                    "use_non_headless": {
                        "type": "boolean",
                        "description": "비헤드리스 모드 사용 여부 (기본값: true)"
                    },
                    "use_human_input": {
                        "type": "boolean",
                        "description": "인간형 입력 사용 여부 (기본값: true)"
                    },
                    "domain": {
                        "type": "string",
                        "description": "쿠키 저장에 사용할 도메인"
                    }
                },
                "required": ["url", "username", "password", "domain"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-login-with-captcha-bypass",
        mappings=[
            {"param_name": "url", "node_type": "attribute", "path": "."},
            {"param_name": "username", "node_type": "attribute", "path": "."},
            {"param_name": "password", "node_type": "attribute", "path": "."},
            {"param_name": "use_cookie_bypass", "node_type": "attribute", "path": "."},
            {"param_name": "use_non_headless", "node_type": "attribute", "path": "."},
            {"param_name": "use_human_input", "node_type": "attribute", "path": "."},
            {"param_name": "domain", "node_type": "attribute", "path": "."}
        ],
        example='''
        <browser-login-with-captcha-bypass 
            url="https://www.lge.com/br/login" 
            username="sadforest@naver.com" 
            password="juni!#18" 
            domain="lge.com" 
            use_cookie_bypass="true" 
            use_non_headless="true" 
            use_human_input="true">
        </browser-login-with-captcha-bypass>
        '''
    )
    async def browser_login_with_captcha_bypass(self, url: str, username: str, password: str, domain: str,
                                           use_cookie_bypass: bool = True, use_non_headless: bool = True,
                                           use_human_input: bool = True) -> ToolResult:
        """
        CAPTCHA 우회 기능을 사용하여 웹사이트에 로그인합니다.
        
        Args:
            url (str): 로그인 페이지 URL
            username (str): 사용자명/이메일
            password (str): 비밀번호
            domain (str): 쿠키 저장에 사용할 도메인
            use_cookie_bypass (bool, optional): 쿠키를 이용한 우회 시도 여부 (기본값: true)
            use_non_headless (bool, optional): 비헤드리스 모드 사용 여부 (기본값: true)
            use_human_input (bool, optional): 인간형 입력 사용 여부 (기본값: true)
            
        Returns:
            ToolResult: 로그인 결과
        """
        try:
            await self._ensure_sandbox()
            
            # 1. 브라우저 설정
            if use_non_headless:
                await self.browser_set_non_headless()
            
            # 2. 쿠키 파일 경로
            cookies_filename = f"{domain.replace('.', '_')}_cookies.json"
            cookies_filepath = os.path.join(self.cookies_dir, cookies_filename)
            
            # 3. 쿠키 우회 시도
            if use_cookie_bypass and os.path.exists(cookies_filepath):
                logger.info(f"저장된 쿠키를 사용하여 로그인 시도: {cookies_filepath}")
                
                # 쿠키 로드
                cookie_result = await self.browser_load_cookies(cookies_filepath)
                
                if cookie_result.get("success", False):
                    # 사이트 접속
                    await self.browser_navigate_to(url)
                    await self.browser_wait(5)
                    
                    # 로그인 상태 확인
                    current_url = await self.browser.evaluate("() => window.location.href")
                    
                    # 쿠키로 로그인 성공 여부 확인 (URL 변경 또는 로그인 요소 부재로 확인)
                    is_logged_in = await self.browser.evaluate("""
                        () => {
                            // 로그인 폼 요소가 없으면 로그인된 것으로 간주
                            const loginForm = document.querySelector('form[action*="login"], form[id*="login"], form[class*="login"]');
                            const usernameField = document.querySelector('input[type="email"], input[type="text"][name*="user"], input[type="text"][name*="email"]');
                            const passwordField = document.querySelector('input[type="password"]');
                            
                            // 로그인 관련 요소가 없으면 로그인 상태로 간주
                            return !loginForm && !usernameField && !passwordField;
                        }
                    """)
                    
                    if is_logged_in:
                        return self.success_response({
                            "message": "쿠키를 사용하여 로그인에 성공했습니다.",
                            "method": "cookie",
                            "current_url": current_url
                        })
                    
                    logger.info("쿠키 로그인 실패, 일반 로그인 시도로 전환합니다.")
            
            # 4. 일반 로그인 시도
            # 사이트 접속
            await self.browser_navigate_to(url)
            await self.browser_wait(5)
            
            # 쿠키 동의 버튼 처리 (있는 경우)
            try:
                cookie_consent = await self.browser.evaluate("""
                    () => {
                        const cookieButtons = Array.from(document.querySelectorAll('button, a'))
                            .filter(el => {
                                const text = el.textContent.toLowerCase();
                                return text.includes('cookie') || text.includes('aceitar') || 
                                       text.includes('accept') || text.includes('consent');
                            });
                        return cookieButtons.length > 0 ? cookieButtons[0] : null;
                    }
                """)
                
                if cookie_consent:
                    cookie_button_index = await self.browser.evaluate("""
                        () => {
                            const elements = document.querySelectorAll('*');
                            const cookieButton = document.querySelector('button, a').filter(el => {
                                const text = el.textContent.toLowerCase();
                                return text.includes('cookie') || text.includes('aceitar') || 
                                       text.includes('accept') || text.includes('consent');
                            })[0];
                            
                            for (let i = 0; i < elements.length; i++) {
                                if (elements[i] === cookieButton) {
                                    return i;
                                }
                            }
                            return -1;
                        }
                    """)
                    
                    if cookie_button_index >= 0:
                        await self.browser_click_element(cookie_button_index)
                        await self.browser_wait(2)
                        
            except Exception as e:
                logger.warning(f"쿠키 동의 버튼 처리 오류 (무시됨): {str(e)}")
            
            # 5. 로그인 폼 요소 탐색
            # 사용자명 필드 찾기
            username_field_index = await self.browser.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    const usernameField = document.querySelector('input[type="email"], input[type="text"][name*="user"], input[type="text"][name*="email"], input[type="text"][id*="user"], input[type="text"][id*="email"]');
                    
                    for (let i = 0; i < elements.length; i++) {
                        if (elements[i] === usernameField) {
                            return i;
                        }
                    }
                    return -1;
                }
            """)
            
            if username_field_index < 0:
                return self.fail_response("사용자명 입력 필드를 찾을 수 없습니다.")
            
            # 비밀번호 필드 찾기
            password_field_index = await self.browser.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    const passwordField = document.querySelector('input[type="password"]');
                    
                    for (let i = 0; i < elements.length; i++) {
                        if (elements[i] === passwordField) {
                            return i;
                        }
                    }
                    return -1;
                }
            """)
            
            if password_field_index < 0:
                return self.fail_response("비밀번호 입력 필드를 찾을 수 없습니다.")
            
            # 6. 로그인 정보 입력
            if use_human_input:
                # 인간형 입력
                await self.browser_human_like_input(username_field_index, username)
                await self.browser_wait(1)
                await self.browser_human_like_input(password_field_index, password)
            else:
                # 일반 입력
                await self.browser_input_text(username_field_index, username)
                await self.browser_wait(1)
                await self.browser_input_text(password_field_index, password)
            
            await self.browser_wait(2)
            
            # 7. CAPTCHA 요소 확인
            captcha_exists = await self.browser.evaluate("""
                () => {
                    // CAPTCHA 관련 요소 탐지
                    const captchaElements = document.querySelectorAll('iframe[src*="recaptcha"], iframe[src*="captcha"], img[alt*="captcha"], div.captcha, div[class*="captcha"]');
                    
                    // CAPTCHA 관련 텍스트 확인
                    const body = document.body.textContent.toLowerCase();
                    const hasCaptchaText = body.includes('captcha') || 
                                        body.includes('security check') || 
                                        body.includes('verificação de segurança') ||
                                        body.includes('texto da imagem') ||
                                        body.includes('human');
                    
                    return {
                        has_elements: captchaElements.length > 0,
                        has_text: hasCaptchaText,
                        element_count: captchaElements.length
                    };
                }
            """)
            
            # 8. 제출 버튼 찾기
            submit_button_index = await self.browser.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    
                    // 로그인 버튼 검색 (여러 선택자 시도)
                    const submitButton = document.querySelector('button[type="submit"], input[type="submit"], button[name*="login"], button[id*="login"], button.login, a.login-button, a[href*="login"]');
                    
                    if (!submitButton) {
                        // 텍스트로 버튼 찾기
                        const buttons = Array.from(document.querySelectorAll('button, input[type="button"], a.btn, a.button, [role="button"]'));
                        const loginButton = buttons.find(btn => {
                            const text = btn.textContent.toLowerCase();
                            return text.includes('login') || text.includes('entrar') || 
                                  text.includes('sign in') || text.includes('log in') ||
                                  text.includes('submit');
                        });
                        
                        if (loginButton) {
                            for (let i = 0; i < elements.length; i++) {
                                if (elements[i] === loginButton) {
                                    return i;
                                }
                            }
                        }
                        return -1;
                    }
                    
                    for (let i = 0; i < elements.length; i++) {
                        if (elements[i] === submitButton) {
                            return i;
                        }
                    }
                    return -1;
                }
            """)
            
            if submit_button_index < 0:
                return self.fail_response("로그인 제출 버튼을 찾을 수 없습니다.")
            
            # 9. CAPTCHA 처리 (있는 경우)
            if captcha_exists.get("has_elements", False) or captcha_exists.get("has_text", False):
                logger.warning("CAPTCHA가 감지되었습니다. 우회를 시도합니다.")
                
                # 페이지 스크린샷 저장
                screenshot_path = os.path.join(self.screenshots_dir, f"captcha_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                await self.browser.screenshot(path=screenshot_path)
                
                # 추가 대기 시간 도입 (자동화 감지 회피)
                await self.browser_wait(3)
                
                # CAPTCHA 이미지 찾기 시도
                captcha_image_index = await self.browser.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('*');
                        const captchaImg = document.querySelector('img[alt*="captcha"], img[src*="captcha"], iframe[src*="captcha"]');
                        
                        if (captchaImg) {
                            for (let i = 0; i < elements.length; i++) {
                                if (elements[i] === captchaImg) {
                                    return i;
                                }
                            }
                        }
                        return -1;
                    }
                """)
                
                # CAPTCHA 입력 필드 찾기 시도
                captcha_input_index = await self.browser.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('*');
                        const captchaInput = document.querySelector('input[name*="captcha"], input[id*="captcha"], input[placeholder*="captcha"], input[aria-label*="captcha"]');
                        
                        if (captchaInput) {
                            for (let i = 0; i < elements.length; i++) {
                                if (elements[i] === captchaInput) {
                                    return i;
                                }
                            }
                        }
                        return -1;
                    }
                """)
                
                # CAPTCHA 가이드 메시지 확인
                captcha_message = await self.browser.evaluate("""
                    () => {
                        const captchaLabels = document.querySelectorAll('label[for*="captcha"], div[class*="captcha"], p[class*="captcha"]');
                        for (const label of captchaLabels) {
                            if (label.textContent.trim()) {
                                return label.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                
                return self.success_response({
                    "message": "로그인 시도 중 CAPTCHA 감지됨",
                    "captcha_detected": True,
                    "screenshot_path": screenshot_path,
                    "captcha_image_index": captcha_image_index,
                    "captcha_input_index": captcha_input_index,
                    "captcha_message": captcha_message,
                    "status": "manual_intervention_required",
                    "note": "CAPTCHA가 감지되어 수동 개입이 필요합니다. 지속적인 자동화 시도는 계정 제한을 초래할 수 있습니다."
                })
            
            # 10. 제출 버튼 클릭
            await self.browser_click_element(submit_button_index)
            await self.browser_wait(5)
            
            # 11. 로그인 결과 확인
            current_url = await self.browser.evaluate("() => window.location.href")
            
            # 로그인 실패 메시지 확인
            error_message = await self.browser.evaluate("""
                () => {
                    // 오류 메시지 찾기
                    const errorElements = document.querySelectorAll('.error, .alert, .message, [role="alert"], [class*="error"], [class*="alert"]');
                    for (const el of errorElements) {
                        if (el.textContent.trim()) {
                            return el.textContent.trim();
                        }
                    }
                    return null;
                }
            """)
            
            if error_message:
                return self.fail_response(f"로그인 실패: {error_message}")
            
            # 로그인 성공 확인
            is_logged_in = await self.browser.evaluate("""
                () => {
                    // 로그인 폼 요소가 없으면 로그인된 것으로 간주
                    const loginForm = document.querySelector('form[action*="login"], form[id*="login"], form[class*="login"]');
                    const usernameField = document.querySelector('input[type="email"], input[type="text"][name*="user"], input[type="text"][name*="email"]');
                    const passwordField = document.querySelector('input[type="password"]');
                    
                    // 로그인 관련 요소가 없으면 로그인 상태로 간주
                    const noLoginElements = !loginForm && !usernameField && !passwordField;
                    
                    // 사용자 계정 관련 요소 확인
                    const accountElements = document.querySelectorAll('[class*="account"], [class*="user"], [class*="profile"], [class*="my-"]');
                    const hasAccountElements = accountElements.length > 0;
                    
                    return noLoginElements || hasAccountElements;
                }
            """)
            
            if is_logged_in:
                # 로그인 성공 시 쿠키 저장
                await self.browser_save_cookies(domain, cookies_filename)
                
                return self.success_response({
                    "message": "로그인에 성공했습니다.",
                    "method": "form",
                    "current_url": current_url
                })
            else:
                return self.fail_response("로그인 절차는 완료되었으나 로그인 상태를 확인할 수 없습니다.")
            
        except Exception as e:
            logger.error(f"로그인 우회 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return self.fail_response(f"로그인 우회 오류: {str(e)}")
