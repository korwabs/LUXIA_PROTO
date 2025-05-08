# LG 브라질 사이트 CAPTCHA 우회 로그인 프롬프트 예제

아래는 LLM에게 LG 브라질 사이트에 로그인하고 마이페이지를 탐색하는 작업을 요청하는 프롬프트 예제입니다. 이 프롬프트는 CAPTCHA 우회 기능을 사용하도록 설계되었습니다.

## 사용자 프롬프트

```
제 LG 브라질 계정으로 로그인하여 마이페이지를 분석해주세요. 
계정 정보는 아래와 같습니다:
- 이메일: sadforest@naver.com
- 비밀번호: juni!#18

로그인 과정에서 CAPTCHA가 있을 수 있으니 우회 기능을 사용해주세요.
로그인 후에는 마이페이지로 이동하여 페이지 구조와 UX/UI 측면에서 분석을 진행해주세요.
특히 다음 사항에 중점을 두고 분석해주세요:
1. 페이지 구조와 주요 기능 영역
2. 사용자 경험(UX) 측면에서의 장단점
3. 인터페이스(UI) 디자인의 효율성과 접근성
4. 개선이 필요한 부분에 대한 제안
```

## 예상 LLM 응답

```
LG 브라질 계정으로 로그인하여 마이페이지를 분석하겠습니다. CAPTCHA 우회 기능을 사용하여 로그인을 시도하겠습니다.

먼저 LG 브라질 사이트에 접속하겠습니다.

<function_calls>
<invoke name="browser_set_non_headless">
<parameter name="user_agent">Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36