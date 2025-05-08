# Google Cloud Platform Credentials

이 디렉토리에는 BigQuery API를 사용하기 위한 Google Cloud Platform의 서비스 계정 키 파일을 저장합니다.

## 설정 방법

1. Google Cloud Console(https://console.cloud.google.com/)에서 서비스 계정을 생성합니다.
2. 서비스 계정에 BigQuery 관련 역할(예: `BigQuery Data Viewer`, `BigQuery Job User`)을 부여합니다.
3. 서비스 계정의 JSON 키 파일을 다운로드합니다.
4. 다운로드한 키 파일을 이 디렉토리에 `service-account.json` 이름으로 저장합니다.

## 주의 사항

- 서비스 계정 키는 절대로 버전 관리 시스템(Git 등)에 포함하지 마세요.
- 이 디렉토리는 `.gitignore`에 포함되어 있어야 합니다.
- 필요한 최소한의 권한만 부여된 서비스 계정을 사용하세요.
- 프로덕션 환경에서는 GCP의 환경 변수 또는 비밀 관리 서비스를 활용하는 것을 고려하세요.

## 환경 변수 설정

Docker Compose 설정에서 다음 환경 변수가 올바르게 설정되어 있는지 확인하세요:

```
BIGQUERY_CREDENTIALS_PATH=/app/gcp-credentials/service-account.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
```

`BIGQUERY_PROJECT_ID`는 GCP 프로젝트 ID로 대체해야 합니다.
