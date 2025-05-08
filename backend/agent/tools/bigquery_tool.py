from google.cloud import bigquery
from google.oauth2 import service_account
from google.cloud.exceptions import Forbidden, NotFound
import os
import json
import re
import sys
import time  # 파일 상단으로 이동
import pathlib
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from agentpress.tool import Tool, ToolResult, openapi_schema, xml_schema
from utils.config import config
import logging
from fuzzywuzzy import process, fuzz  # 문자열 유사도 측정 라이브러리

logger = logging.getLogger(__name__)

class BigQueryTool(Tool):
    """Tool for executing BigQuery SQL queries against Google Cloud Platform."""

    def __init__(self, credentials_path: str = None, project_id: str = None, location: str = None):
        super().__init__()
        # Load environment variables
        load_dotenv()
        
        # 환경변수에서 설정을 가져오거나 매개변수로 전달된 값 사용
        self.credentials_path = credentials_path or config.get('BIGQUERY_CREDENTIALS_PATH')
        self.project_id = project_id or config.get('BIGQUERY_PROJECT_ID')
        self.location = location or config.get('BIGQUERY_LOCATION')
        
        if not self.credentials_path:
            raise ValueError("BIGQUERY_CREDENTIALS_PATH not found in configuration or provided as parameter")
        if not self.project_id:
            raise ValueError("BIGQUERY_PROJECT_ID not found in configuration or provided as parameter")
            
        # 서비스 계정 키 파일 검증
        self._validate_credentials_file()
        
        # 프로젝트 ID 형식 검증
        self._validate_project_id()
        
        # BigQuery 클라이언트 초기화
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            self.client = bigquery.Client(
                credentials=credentials, 
                project=self.project_id,
                location=self.location
            )
            logger.info(f"BigQuery client initialized for project: {self.project_id}, location: {self.location or 'default'}")
            
            # 권한 검사 수행 - 이는 Docker 로그에 표시됨
            auth_status = self._check_permissions()
            for log_line in auth_status:
                # 두 가지 로그 방식 모두 사용 (logger와 stdout)
                logger.info(log_line)
                print(log_line, file=sys.stderr)  # Docker 로그에 출력
                
        except Exception as e:
            error_message = f"Failed to initialize BigQuery client: {str(e)}"
            logger.error(error_message)
            print(f"[BIGQUERY_AUTH_ERROR] {error_message}", file=sys.stderr)  # Docker 로그에 출력
            raise ValueError(error_message)
    
    def _check_permissions(self) -> List[str]:
        """
        BigQuery 권한을 검사하고 권한 상태에 대한 로그 메시지 목록을 반환합니다.
        """
        log_messages = []
        log_messages.append(f"[BIGQUERY_AUTH_CHECK] Checking permissions for project: {self.project_id}")
        
        # 서비스 계정 정보 확인
        try:
            service_account_email = None
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
                service_account_email = creds_data.get('client_email')
            
            if service_account_email:
                log_messages.append(f"[BIGQUERY_AUTH_INFO] Using service account: {service_account_email}")
            else:
                log_messages.append("[BIGQUERY_AUTH_WARNING] Service account email not found in credentials file")
        except Exception as e:
            log_messages.append(f"[BIGQUERY_AUTH_WARNING] Error reading service account details: {str(e)}")
        
        # 1. 데이터셋 리스팅 권한 확인
        try:
            # 리스트만 확인하고 실제 데이터는 가져오지 않음
            datasets = list(self.client.list_datasets(max_results=1))
            log_messages.append(f"[BIGQUERY_AUTH_SUCCESS] Successfully listed datasets in project {self.project_id}")
        except Forbidden as e:
            log_messages.append(f"[BIGQUERY_AUTH_ERROR] Permission denied: Cannot list datasets. Error: {str(e)}")
            log_messages.append("[BIGQUERY_AUTH_TIP] Service account needs 'BigQuery Data Viewer' or 'BigQuery User' role")
        except Exception as e:
            log_messages.append(f"[BIGQUERY_AUTH_ERROR] Error listing datasets: {str(e)}")
        
        # 2. 쿼리 실행 권한 확인 - 간단한 SELECT 1 실행
        try:
            query_job = self.client.query("SELECT 1 AS test")
            # 결과 가져오기
            query_job.result()
            log_messages.append("[BIGQUERY_AUTH_SUCCESS] Successfully executed test query")
        except Forbidden as e:
            log_messages.append(f"[BIGQUERY_AUTH_ERROR] Permission denied: Cannot execute queries. Error: {str(e)}")
            log_messages.append("[BIGQUERY_AUTH_TIP] Service account needs 'BigQuery Job User' role for running queries")
        except Exception as e:
            log_messages.append(f"[BIGQUERY_AUTH_ERROR] Error executing test query: {str(e)}")
        
        return log_messages
    
    def _log_auth_info(self, message: str):
        """
        권한 관련 정보를 로그에 기록하고 Docker 로그에도 출력합니다.
        """
        logger.info(message)
        print(message, file=sys.stderr)  # stderr로 출력하면 Docker 로그에 표시됨

    def _validate_credentials_file(self) -> None:
        """서비스 계정 키 파일 유효성 검증"""
        try:
            # 파일 존재 및 접근 가능 여부 확인
            cred_path = pathlib.Path(self.credentials_path)
            if not cred_path.exists():
                raise ValueError(f"서비스 계정 키 파일을 찾을 수 없습니다: {self.credentials_path}")
            if not os.access(self.credentials_path, os.R_OK):
                raise ValueError(f"서비스 계정 키 파일에 접근할 수 없습니다: {self.credentials_path}. 파일 권한을 확인하세요.")
            
            # 파일 내용 검증
            with open(self.credentials_path, 'r') as f:
                key_data = json.load(f)
                
            # 기본 키 파일 구조 검증
            if not key_data.get('type') or key_data.get('type') != 'service_account' or not key_data.get('project_id'):
                raise ValueError('유효하지 않은 서비스 계정 키 파일 형식입니다.')
                
            logger.info(f"서비스 계정 키 파일 검증 완료: {self.credentials_path}")
        except json.JSONDecodeError:
            raise ValueError('서비스 계정 키 파일이 유효한 JSON 형식이 아닙니다.')
        except Exception as e:
            logger.error(f"서비스 계정 키 파일 검증 오류: {str(e)}")
            raise
    
    def _validate_project_id(self) -> None:
        """프로젝트 ID 형식 검증"""
        if not self.project_id or not re.match(r'^[a-z0-9-]+$', self.project_id):
            raise ValueError(f"유효하지 않은 프로젝트 ID 형식입니다: {self.project_id}")
        logger.info(f"프로젝트 ID 검증 완료: {self.project_id}")
    
    def _is_read_only_query(self, query: str) -> bool:
        """쿼리가 읽기 전용인지 확인"""
        forbidden_pattern = r'\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|MERGE|TRUNCATE|GRANT|REVOKE|EXECUTE|BEGIN|COMMIT|ROLLBACK)\b'
        return not bool(re.search(forbidden_pattern, query, re.IGNORECASE))
    
    def _qualify_information_schema_query(self, query: str) -> str:
        """INFORMATION_SCHEMA 쿼리에 프로젝트 ID 추가"""
        if 'INFORMATION_SCHEMA' in query.upper():
            # FROM INFORMATION_SCHEMA.TABLES 또는 FROM dataset.INFORMATION_SCHEMA.TABLES 매치
            unqualified_pattern = r'FROM\s+(?:(\w+)\.)?INFORMATION_SCHEMA\.TABLES'
            
            def replace_match(match):
                dataset = match.group(1)
                if dataset:
                    return f"FROM `{self.project_id}.{dataset}.INFORMATION_SCHEMA.TABLES`"
                else:
                    raise ValueError("INFORMATION_SCHEMA 쿼리 시 데이터셋을 지정해야 합니다 (예: dataset.INFORMATION_SCHEMA.TABLES)")
            
            query = re.sub(unqualified_pattern, replace_match, query, flags=re.IGNORECASE)
        
        return query
    
    # 헬퍼 메서드를 클래스 상단부로 이동
    async def _get_all_datasets(self) -> List[Dict[str, Any]]:
        """모든 데이터셋 정보를 가져오는 내부 헬퍼 메서드"""
        result = await self.list_datasets()
        if result.is_error:
            return []
        return result.result.get("datasets", [])
    
    async def _get_all_tables(self) -> List[Dict[str, Any]]:
        """모든 테이블 정보를 가져오는 내부 헬퍼 메서드"""
        all_tables = []
        datasets = await self._get_all_datasets()
        
        for dataset in datasets:
            dataset_id = dataset.get("id", "")
            if not dataset_id:
                continue
                
            tables_result = await self.list_tables(dataset_id=dataset_id)
            if tables_result.is_error:
                continue
                
            tables = tables_result.result.get("tables", [])
            for table in tables:
                table["dataset_id"] = dataset_id  # 데이터셋 ID 추가
            
            all_tables.extend(tables)
            
        return all_tables

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": "Execute a SQL query against BigQuery to retrieve data from Google Analytics or other datasets. This tool allows you to query data stored in BigQuery tables for analytics, reporting, and insight generation. Results include the data retrieved from the query, with proper handling of various data types, including nested structures. Only READ operations (SELECT queries) are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute against BigQuery. Use standard SQL syntax compatible with Google BigQuery. Include proper table references in the format `project_id.dataset_id.table_id`. Only SELECT queries are permitted."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of results to return. Default is 1000. Maximum allowed is 10000.",
                        "default": 1000
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "The timeout for the query execution in milliseconds. Default is 60000 (60 seconds). Maximum allowed is 300000 (5 minutes).",
                        "default": 60000
                    }
                },
                "required": ["query"]
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-execute",
        mappings=[
            {"param_name": "query", "node_type": "element", "path": "query"},
            {"param_name": "max_results", "node_type": "attribute", "path": ".", "required": False},
            {"param_name": "timeout_ms", "node_type": "attribute", "path": ".", "required": False}
        ],
        example='''
        <!-- 
        The bigquery-execute tool allows you to query data stored in BigQuery.
        Use this tool to analyze Google Analytics data, marketing data, and other datasets stored in GCP.
        
        The tool returns the data retrieved from the query in a structured format.
        -->
        
        <!-- Simple query example -->
        <bigquery-execute max_results="100" timeout_ms="30000">
            <query>
                SELECT date, count(*) as visit_count 
                FROM `project_id.dataset_id.ga_sessions_*` 
                WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20240131'
                GROUP BY date 
                ORDER BY date
            </query>
        </bigquery-execute>
        
        <!-- Another query example for product data -->
        <bigquery-execute>
            <query>
                SELECT product_id, product_name, SUM(quantity) as total_quantity, SUM(revenue) as total_revenue
                FROM `project_id.dataset_id.product_sales`
                GROUP BY product_id, product_name
                ORDER BY total_revenue DESC
                LIMIT 10
            </query>
        </bigquery-execute>
        '''
    )
    async def execute_query(
        self,
        query: str,
        max_results: int = 1000,
        timeout_ms: int = 60000
    ) -> ToolResult:
        """
        Execute a SQL query against BigQuery and return the results.
        
        This function runs the specified SQL query against the configured BigQuery project
        and returns the query results. The results are formatted for easy consumption
        and include all retrieved data rows, column names, and types.
        
        Parameters:
        - query: The SQL query to execute
        - max_results: Maximum number of results to return (default: 1000)
        - timeout_ms: Query timeout in milliseconds (default: 60000)
        """
        try:
            # 입력 유효성 검사
            if not query or not isinstance(query, str):
                return self.fail_response("유효한 SQL 쿼리가 필요합니다.")
            
            # 읽기 전용 쿼리 검증
            if not self._is_read_only_query(query):
                return self.fail_response("읽기 전용(SELECT) 쿼리만 허용됩니다.")
            
            # INFORMATION_SCHEMA 쿼리 처리
            try:
                query = self._qualify_information_schema_query(query)
            except ValueError as e:
                return self.fail_response(str(e))
            
            # max_results 정규화
            if max_results is None:
                max_results = 1000
            elif isinstance(max_results, int):
                max_results = max(1, min(max_results, 10000))  # 최대 10,000개로 제한
            elif isinstance(max_results, str):
                try:
                    max_results = max(1, min(int(max_results), 10000))
                except ValueError:
                    max_results = 1000
            else:
                max_results = 1000
            
            # timeout_ms 정규화
            if timeout_ms is None:
                timeout_ms = 60000
            elif isinstance(timeout_ms, int):
                timeout_ms = max(1000, min(timeout_ms, 300000))  # 1초~5분 사이로 제한
            elif isinstance(timeout_ms, str):
                try:
                    timeout_ms = max(1000, min(int(timeout_ms), 300000))
                except ValueError:
                    timeout_ms = 60000
            else:
                timeout_ms = 60000
            
            # 쿼리 실행 전 로그
            log_message = f"Executing BigQuery query with max_results={max_results}, timeout_ms={timeout_ms}"
            logger.info(log_message)
            print(f"[BIGQUERY_QUERY] {log_message}", file=sys.stderr)  # Docker 로그에 출력
            
            # 쿼리 처리 시작 시간 기록
            start_time = time.time()
            
            # 쿼리 작업 구성
            job_config = bigquery.QueryJobConfig()
            
            # API 버전 호환성을 위한 설정
            try:
                # 문자열이 아닌 정수로 설정
                job_config.maximum_bytes_billed = 10000000000  # 제한 없음
            except AttributeError:
                logger.debug("maximum_bytes_billed not available in this API version")
            
            try:
                job_config.max_results = max_results
            except AttributeError:
                try:
                    job_config.maximum_results = max_results
                except AttributeError:
                    logger.debug("Neither max_results nor maximum_results available")
            
            # 쿼리 실행
            try:
                query_job = self.client.query(
                    query,
                    job_config=job_config,
                    timeout=timeout_ms / 1000  # 밀리초를 초로 변환
                )
            except Forbidden as e:
                error_msg = f"Permission denied: {str(e)}"
                self._log_auth_info(f"[BIGQUERY_AUTH_ERROR] {error_msg}")
                self._log_auth_info("[BIGQUERY_AUTH_TIP] Check if service account has 'BigQuery Job User' role")
                return self.fail_response(f"BigQuery 권한 부족: {error_msg}")
            
            # 결과 가져오기
            try:
                results = query_job.result()
            except Forbidden as e:
                error_msg = f"Permission denied when fetching results: {str(e)}"
                self._log_auth_info(f"[BIGQUERY_AUTH_ERROR] {error_msg}")
                self._log_auth_info("[BIGQUERY_AUTH_TIP] Check if service account has 'BigQuery Data Viewer' role")
                return self.fail_response(f"BigQuery 결과 가져오기 권한 부족: {error_msg}")
            
            # 쿼리 실행 시간 계산
            query_time = time.time() - start_time
            print(f"[BIGQUERY_QUERY_TIME] {query_time:.2f} seconds", file=sys.stderr)  # Docker 로그에 출력
            
            # 결과를 딕셔너리 목록으로 변환
            rows = []
            for row in results:
                row_dict = {}
                for key, value in row.items():
                    # BigQuery의 특수 타입 처리 (TIMESTAMP, STRUCT 등)
                    if hasattr(value, 'isoformat'):  # datetime 객체 처리
                        row_dict[key] = value.isoformat()
                    elif isinstance(value, (dict, list)):  # 중첩 구조 처리
                        row_dict[key] = json.dumps(value)
                    else:
                        row_dict[key] = value
                rows.append(row_dict)
            
            # 쿼리 메타데이터와 함께 결과 반환
            result_data = {
                "query": query,
                "num_rows": len(rows),
                "query_time_seconds": round(query_time, 2),
                "schema": [field.name for field in results.schema],
                "data": rows
            }
            
            # 결과 수 로그
            print(f"[BIGQUERY_RESULT] Query returned {len(rows)} rows in {query_time:.2f} seconds", file=sys.stderr)
            
            return self.success_response(result_data)
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"Error executing BigQuery query: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_datasets",
            "description": "List all available datasets in the configured BigQuery project. This tool provides information about the datasets accessible to the service account, including dataset IDs and creation timestamps.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-list-datasets",
        mappings=[],
        example='''
        <!-- 
        The bigquery-list-datasets tool allows you to list all available datasets in the configured BigQuery project.
        Use this tool to explore the available datasets before querying them.
        
        The tool returns a list of datasets with their IDs and creation timestamps.
        -->
        
        <!-- List all datasets -->
        <bigquery-list-datasets></bigquery-list-datasets>
        '''
    )
    async def list_datasets(self) -> ToolResult:
        """
        List all available datasets in the configured BigQuery project.
        
        This function returns information about all datasets accessible to the 
        service account in the configured project, including dataset IDs and
        creation timestamps.
        """
        try:
            datasets = list(self.client.list_datasets())
            
            if not datasets:
                return self.success_response({
                    "message": "No datasets found in project",
                    "datasets": []
                })
            
            dataset_list = []
            for dataset in datasets:
                # 데이터셋 정보 추출 (사용 가능한 속성만 추출)
                dataset_info = {
                    "id": dataset.dataset_id,
                    "full_id": dataset.full_dataset_id
                }
                
                # 옵션널 속성들 추가
                if hasattr(dataset, 'friendly_name'):
                    dataset_info["friendly_name"] = dataset.friendly_name
                    
                # 개별 데이터셋 정보를 가져와서 추가 정보 추출
                try:
                    # 데이터셋 상세 정보 가져오기
                    full_dataset = self.client.get_dataset(dataset.reference)
                    if hasattr(full_dataset, 'location') and full_dataset.location:
                        dataset_info["location"] = full_dataset.location
                except Exception as e:
                    logger.warning(f"Could not get additional info for dataset {dataset.dataset_id}: {str(e)}")
                
                dataset_list.append(dataset_info)
            
            return self.success_response({
                "message": f"Found {len(dataset_list)} datasets",
                "datasets": dataset_list
            })
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"Error listing BigQuery datasets: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all tables in a specified BigQuery dataset. This tool provides information about the tables available in a dataset, including table IDs, row counts (if available), and creation timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "The ID of the dataset to list tables from. Do not include the project ID."
                    }
                },
                "required": ["dataset_id"]
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-list-tables",
        mappings=[
            {"param_name": "dataset_id", "node_type": "attribute", "path": "."}
        ],
        example='''
        <!-- 
        The bigquery-list-tables tool allows you to list all tables in a specified BigQuery dataset.
        Use this tool to explore the available tables in a dataset before querying them.
        
        The tool returns a list of tables with their IDs and metadata.
        -->
        
        <!-- List all tables in a dataset -->
        <bigquery-list-tables dataset_id="analytics_data"></bigquery-list-tables>
        '''
    )
    async def list_tables(self, dataset_id: str) -> ToolResult:
        """
        List all tables in a specified BigQuery dataset.
        
        This function returns information about all tables in the specified dataset,
        including table IDs, row counts (if available), and creation timestamps.
        
        Parameters:
        - dataset_id: The ID of the dataset to list tables from
        """
        try:
            if not dataset_id:
                return self.fail_response("A valid dataset ID is required.")
            
            dataset_ref = self.client.dataset(dataset_id)
            tables = list(self.client.list_tables(dataset_ref))
            
            if not tables:
                return self.success_response({
                    "message": f"No tables found in dataset '{dataset_id}'",
                    "tables": []
                })
            
            table_list = []
            for table in tables:
                try:
                    # 테이블 정보 가져오기
                    table_ref = self.client.get_table(table.reference)
                    
                    # 기본 테이블 정보
                    table_info = {
                        "id": table.table_id,
                        "full_id": f"{self.project_id}.{dataset_id}.{table.table_id}"
                    }
                    
                    # 테이블 타입
                    if hasattr(table, 'table_type'):
                        table_info["type"] = table.table_type
                    
                    # 테이블 행 수
                    if hasattr(table_ref, 'num_rows'):
                        table_info["num_rows"] = table_ref.num_rows
                    
                    # 테이블 크기
                    if hasattr(table_ref, 'num_bytes'):
                        table_info["size_bytes"] = table_ref.num_bytes
                    
                    # 생성 시간
                    if hasattr(table_ref, 'created') and table_ref.created:
                        table_info["creation_time"] = table_ref.created.isoformat()
                    
                    # 수정 시간
                    if hasattr(table_ref, 'modified') and table_ref.modified:
                        table_info["last_modified"] = table_ref.modified.isoformat()
                    
                    table_list.append(table_info)
                except Exception as e:
                    logger.warning(f"Could not get full details for table {table.table_id}: {str(e)}")
                    # 기본 정보만 추가
                    table_list.append({
                        "id": table.table_id,
                        "full_id": f"{self.project_id}.{dataset_id}.{table.table_id}"
                    })
            
            return self.success_response({
                "message": f"Found {len(table_list)} tables in dataset '{dataset_id}'",
                "tables": table_list
            })
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"Error listing BigQuery tables: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "get_table_schema",
            "description": "Get the schema of a specified BigQuery table. This tool provides detailed information about the structure of a table, including field names, data types, descriptions, and mode (NULLABLE, REQUIRED, REPEATED).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "The ID of the dataset containing the table. Do not include the project ID."
                    },
                    "table_id": {
                        "type": "string",
                        "description": "The ID of the table to get the schema for."
                    }
                },
                "required": ["dataset_id", "table_id"]
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-get-schema",
        mappings=[
            {"param_name": "dataset_id", "node_type": "attribute", "path": "."},
            {"param_name": "table_id", "node_type": "attribute", "path": "."}
        ],
        example='''
        <!-- 
        The bigquery-get-schema tool allows you to get the schema of a specified BigQuery table.
        Use this tool to understand the structure of a table before querying it.
        
        The tool returns detailed information about the fields in the table, including names, types, and descriptions.
        -->
        
        <!-- Get the schema of a table -->
        <bigquery-get-schema dataset_id="analytics_data" table_id="ga_sessions"></bigquery-get-schema>
        '''
    )
    async def get_table_schema(self, dataset_id: str, table_id: str) -> ToolResult:
        """
        Get the schema of a specified BigQuery table.
        
        This function returns detailed information about the structure of a table,
        including field names, data types, descriptions, and mode (NULLABLE, REQUIRED, REPEATED).
        
        Parameters:
        - dataset_id: The ID of the dataset containing the table
        - table_id: The ID of the table to get the schema for
        """
        try:
            if not dataset_id or not table_id:
                return self.fail_response("유효한 데이터셋 ID와 테이블 ID가 필요합니다.")
            
            try:
                table_ref = self.client.dataset(dataset_id).table(table_id)
                table = self.client.get_table(table_ref)
            except Exception as e:
                if "404" in str(e) or "Not found" in str(e):
                    return self.fail_response(f"테이블을 찾을 수 없습니다: {self.project_id}.{dataset_id}.{table_id}. 테이블 ID가 정확한지 확인하거나 테이블 접근 권한을 확인하세요.")
                else:
                    raise
            
            # 스키마 정보 추출 함수 (재귀적으로 중첩 필드 처리)
            def extract_field_info(field):
                field_info = {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description
                }
                
                # 중첩 필드 처리
                if field.field_type == "RECORD" and field.fields:
                    nested_fields = []
                    for nested_field in field.fields:
                        nested_fields.append(extract_field_info(nested_field))
                    field_info["fields"] = nested_fields
                
                return field_info
            
            schema_fields = [extract_field_info(field) for field in table.schema]
            
            table_info = {
                "full_id": f"{self.project_id}.{dataset_id}.{table_id}",
                "description": table.description,
                "num_rows": table.num_rows,
                "size_bytes": table.num_bytes,
                "type": table.table_type if hasattr(table, 'table_type') else None,
                "creation_time": table.created.isoformat() if hasattr(table, 'created') and table.created else None,
                "last_modified": table.modified.isoformat() if hasattr(table, 'modified') and table.modified else None,
                "schema": schema_fields
            }
            
            return self.success_response(table_info)
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"Error getting BigQuery table schema: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)


    @openapi_schema({
        "type": "function",
        "function": {
            "name": "search_resources",
            "description": "자연어 키워드로 데이터셋, 테이블 또는 필드를 검색합니다. 정확한 이름을 모를 때 유용하며, 검색어와 유사한 리소스를 찾아 SQL 쿼리 작성에 도움을 줍니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "검색할 키워드. 데이터셋, 테이블 또는 필드 이름에 관련된 자연어 키워드."
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "검색할 리소스 유형. 'dataset', 'table' 또는 'field' 중 하나.",
                        "enum": ["dataset", "table", "field", "all"],
                        "default": "all"
                    },
                    "min_similarity": {
                        "type": "integer",
                        "description": "최소 유사도 점수(0-100). 기본값은 60.",
                        "default": 60
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "반환할 최대 결과 수. 기본값은 10.",
                        "default": 10
                    }
                },
                "required": ["keywords"]
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-search",
        mappings=[
            {"param_name": "keywords", "node_type": "element", "path": "keywords"},
            {"param_name": "resource_type", "node_type": "attribute", "path": ".", "required": False},
            {"param_name": "min_similarity", "node_type": "attribute", "path": ".", "required": False},
            {"param_name": "max_results", "node_type": "attribute", "path": ".", "required": False}
        ],
        example='''
        <!-- 
        The bigquery-search tool allows you to search for datasets, tables, or fields using natural language keywords.
        This is useful when you don't know the exact names of resources but need to find them for analysis.
        
        The tool returns a list of resources that match your keywords, along with their similarity scores.
        -->
        
        <!-- Search for tables related to user sessions -->
        <bigquery-search resource_type="table" min_similarity="70" max_results="5">
            <keywords>user sessions website visits</keywords>
        </bigquery-search>
        
        <!-- Search for fields related to revenue -->
        <bigquery-search resource_type="field">
            <keywords>revenue sales income</keywords>
        </bigquery-search>
        '''
    )
    async def search_resources(
        self,
        keywords: str,
        resource_type: str = "all",
        min_similarity: int = 60,
        max_results: int = 10
    ) -> ToolResult:
        """
        자연어 키워드로 BigQuery 리소스(데이터셋, 테이블, 필드)를 검색합니다.
        
        이 함수는 키워드와 가장 유사한 리소스를 찾아 반환합니다. 정확한 이름을 모를 때 유용합니다.
        
        Parameters:
        - keywords: 검색할 키워드
        - resource_type: 검색할 리소스 유형 ('dataset', 'table', 'field', 'all' 중 하나)
        - min_similarity: 최소 유사도 점수 (0-100)
        - max_results: 반환할 최대 결과 수
        """
        try:
            if not keywords or not isinstance(keywords, str):
                return self.fail_response("유효한 검색 키워드가 필요합니다.")
            
            # 리소스 타입 유효성 검사
            valid_resource_types = ["dataset", "table", "field", "all"]
            if resource_type not in valid_resource_types:
                return self.fail_response(f"유효하지 않은 resource_type: {resource_type}. 'dataset', 'table', 'field', 'all' 중 하나여야 합니다.")
            
            # 유사도 점수 정규화
            min_similarity = max(0, min(100, min_similarity))
            
            # 결과 수 정규화
            max_results = max(1, min(50, max_results))
            
            # 키워드 전처리
            keywords = keywords.lower()
            search_terms = keywords.split()
            
            results = {}
            
            # 데이터셋 검색
            if resource_type in ["dataset", "all"]:
                datasets = await self._get_all_datasets()
                dataset_matches = []
                
                for dataset in datasets:
                    dataset_id = dataset.get("id", "")
                    dataset_name = dataset_id.lower()
                    
                    # 유사도 계산 (각 검색어에 대한 최대 유사도 점수 사용)
                    similarity_scores = []
                    for term in search_terms:
                        term_similarity = fuzz.partial_ratio(term, dataset_name)
                        similarity_scores.append(term_similarity)
                    
                    # 평균 유사도 점수
                    avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
                    
                    if avg_similarity >= min_similarity:
                        dataset_matches.append({
                            "id": dataset_id,
                            "full_id": dataset.get("full_id", ""),
                            "type": "dataset",
                            "similarity": avg_similarity
                        })
                
                # 유사도 점수로 정렬
                dataset_matches.sort(key=lambda x: x["similarity"], reverse=True)
                results["datasets"] = dataset_matches[:max_results]
            
            # 테이블 검색
            table_matches = []
            if resource_type in ["table", "all"]:
                # 모든 데이터셋에서 테이블 가져오기
                all_tables = await self._get_all_tables()
                
                for table in all_tables:
                    table_id = table.get("id", "")
                    dataset_id = table.get("dataset_id", "")
                    full_id = table.get("full_id", "")
                    table_name = table_id.lower()
                    
                    # 유사도 계산
                    similarity_scores = []
                    for term in search_terms:
                        term_similarity = fuzz.partial_ratio(term, table_name)
                        similarity_scores.append(term_similarity)
                    
                    avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
                    
                    if avg_similarity >= min_similarity:
                        table_matches.append({
                            "id": table_id,
                            "dataset_id": dataset_id,
                            "full_id": full_id,
                            "type": "table",
                            "similarity": avg_similarity
                        })
                
                # 유사도 점수로 정렬
                table_matches.sort(key=lambda x: x["similarity"], reverse=True)
                results["tables"] = table_matches[:max_results]
            
            # 필드 검색
            field_matches = []
            if resource_type in ["field", "all"]:
                # 검색된 테이블 또는 모든 테이블에서 필드 가져오기
                tables_to_check = table_matches[:min(5, len(table_matches))] if table_matches else all_tables[:min(10, len(all_tables)) if 'all_tables' in locals() else 0]
                
                for table in tables_to_check:
                    try:
                        table_id = table.get("id", "")
                        dataset_id = table.get("dataset_id", "")
                        
                        # 테이블 스키마 가져오기
                        schema_result = await self.get_table_schema(dataset_id=dataset_id, table_id=table_id)
                        if schema_result.is_error:
                            continue
                        
                        schema_fields = schema_result.result.get("schema", [])
                        
                        for field in schema_fields:
                            field_name = field.get("name", "").lower()
                            field_description = field.get("description", "").lower()
                            
                            # 필드 이름과 설명에 대한 유사도 계산
                            name_scores = []
                            desc_scores = []
                            
                            for term in search_terms:
                                name_score = fuzz.partial_ratio(term, field_name)
                                name_scores.append(name_score)
                                
                                if field_description:
                                    desc_score = fuzz.partial_ratio(term, field_description)
                                    desc_scores.append(desc_score)
                            
                            avg_name_similarity = sum(name_scores) / len(name_scores) if name_scores else 0
                            avg_desc_similarity = sum(desc_scores) / len(desc_scores) if desc_scores else 0
                            
                            # 이름과 설명 유사도의 가중 평균 (이름에 더 높은 가중치)
                            overall_similarity = (avg_name_similarity * 0.7) + (avg_desc_similarity * 0.3) if desc_scores else avg_name_similarity
                            
                            if overall_similarity >= min_similarity:
                                field_matches.append({
                                    "name": field.get("name", ""),
                                    "type": field.get("type", ""),
                                    "mode": field.get("mode", ""),
                                    "description": field.get("description", ""),
                                    "table_id": table_id,
                                    "dataset_id": dataset_id,
                                    "full_reference": f"{dataset_id}.{table_id}.{field.get('name', '')}",
                                    "resource_type": "field",
                                    "similarity": overall_similarity
                                })
                    except Exception as e:
                        logger.warning(f"필드 정보 추출 중 오류: {str(e)}")
                        continue
                
                # 유사도 점수로 정렬
                field_matches.sort(key=lambda x: x["similarity"], reverse=True)
                results["fields"] = field_matches[:max_results]
            
            # 통합 결과 생성
            all_matches = []
            for resource_type, matches in results.items():
                if matches:
                    all_matches.extend(matches)
            
            # 전체 결과를 유사도 점수로 정렬
            all_matches.sort(key=lambda x: x["similarity"], reverse=True)
            
            if not all_matches:
                return self.success_response({
                    "message": f"키워드 '{keywords}'에 대한 검색 결과가 없습니다. 다른 키워드를 시도해 보세요.",
                    "results": []
                })
            
            return self.success_response({
                "message": f"키워드 '{keywords}'에 대한 검색 결과 {len(all_matches)}개를 찾았습니다.",
                "search_params": {
                    "keywords": keywords,
                    "resource_type": resource_type,
                    "min_similarity": min_similarity
                },
                "results": all_matches[:max_results]
            })
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"리소스 검색 중 오류: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "generate_query",
            "description": "자연어 설명을 바탕으로 BigQuery SQL 쿼리를 생성합니다. 테이블과 필드 정보를 찾아 쿼리를 구성하고, 가능하면 실행할 준비가 된 SQL 문을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "생성할 쿼리에 대한 자연어 설명. 예: '지난 30일간 일별 방문자 수 집계'"
                    },
                    "dataset_hint": {
                        "type": "string",
                        "description": "사용할 데이터셋에 대한 힌트(선택 사항). 없으면 키워드를 기반으로 검색합니다.",
                        "optional": True
                    },
                    "table_hint": {
                        "type": "string",
                        "description": "사용할 테이블에 대한 힌트(선택 사항). 없으면 키워드를 기반으로 검색합니다.",
                        "optional": True
                    }
                },
                "required": ["description"]
            }
        }
    })
    @xml_schema(
        tag_name="bigquery-generate-query",
        mappings=[
            {"param_name": "description", "node_type": "element", "path": "description"},
            {"param_name": "dataset_hint", "node_type": "attribute", "path": ".", "required": False},
            {"param_name": "table_hint", "node_type": "attribute", "path": ".", "required": False}
        ],
        example='''
        <!-- 
        The bigquery-generate-query tool helps you create SQL queries from natural language descriptions.
        This is useful when you know what data you want but don't know the exact SQL syntax.
        
        The tool returns a ready-to-use SQL query based on your description and available tables/fields.
        -->
        
        <!-- Generate a query to count daily visits -->
        <bigquery-generate-query dataset_hint="analytics_data" table_hint="ga_sessions">
            <description>Count the number of users per day over the last 30 days</description>
        </bigquery-generate-query>
        
        <!-- Generate a query for product revenue analysis -->
        <bigquery-generate-query>
            <description>Find top 10 products by revenue in 2023</description>
        </bigquery-generate-query>
        '''
    )
    async def generate_query(
        self,
        description: str,
        dataset_hint: str = None,
        table_hint: str = None
    ) -> ToolResult:
        """
        자연어 설명을 바탕으로 BigQuery SQL 쿼리를 생성합니다.
        
        이 함수는 사용자의 자연어 설명을 분석하고, 적절한 테이블과 필드를 찾아
        실행 가능한 SQL 쿼리를 생성합니다.
        
        Parameters:
        - description: 생성할 쿼리에 대한 자연어 설명
        - dataset_hint: 사용할 데이터셋에 대한 힌트(선택 사항)
        - table_hint: 사용할 테이블에 대한 힌트(선택 사항)
        """
        try:
            if not description or not isinstance(description, str):
                return self.fail_response("유효한 쿼리 설명이 필요합니다.")
            
            # 1. 키워드 추출 및 관련 데이터셋/테이블 검색
            keywords = description.lower()
            dataset_matches = []
            table_matches = []
            field_info = {}
            
            # 데이터셋 힌트가 있는 경우 해당 데이터셋 사용
            if dataset_hint:
                try:
                    datasets = await self._get_all_datasets()
                    for dataset in datasets:
                        if dataset_hint.lower() in dataset.get("id", "").lower():
                            dataset_matches.append(dataset)
                            break
                except Exception as e:
                    logger.warning(f"데이터셋 힌트 처리 중 오류: {str(e)}")
            
            # 데이터셋을 찾지 못했으면 검색
            if not dataset_matches:
                search_result = await self.search_resources(keywords=description, resource_type="dataset", max_results=3)
                if not search_result.is_error and search_result.result.get("results"):
                    dataset_matches = search_result.result.get("results")
            
            # 테이블 힌트가 있는 경우 해당 테이블 사용
            if table_hint:
                try:
                    all_tables = []
                    if dataset_matches:
                        for dataset in dataset_matches:
                            dataset_id = dataset.get("id", "")
                            tables_result = await self.list_tables(dataset_id=dataset_id)
                            if not tables_result.is_error:
                                all_tables.extend(tables_result.result.get("tables", []))
                    else:
                        all_tables = await self._get_all_tables()
                    
                    for table in all_tables:
                        if table_hint.lower() in table.get("id", "").lower():
                            table_matches.append(table)
                            break
                except Exception as e:
                    logger.warning(f"테이블 힌트 처리 중 오류: {str(e)}")
            
            # 테이블을 찾지 못했으면 검색
            if not table_matches:
                search_result = await self.search_resources(keywords=description, resource_type="table", max_results=3)
                if not search_result.is_error and search_result.result.get("results"):
                    table_matches = search_result.result.get("results")
            
            # 매칭되는 테이블이 없으면 실패
            if not table_matches:
                return self.fail_response(
                    "쿼리를 생성할 수 없습니다. 적절한 테이블을 찾지 못했습니다. " +
                    "더 구체적인 설명이나 테이블 힌트를 제공해 주세요."
                )
            
            # 2. 각 테이블의 스키마 정보 수집
            for table in table_matches:
                table_id = table.get("id", "")
                dataset_id = table.get("dataset_id", "")
                
                # 스키마 가져오기
                try:
                    schema_result = await self.get_table_schema(dataset_id=dataset_id, table_id=table_id)
                    if not schema_result.is_error:
                        schema_fields = schema_result.result.get("schema", [])
                        field_info[f"{dataset_id}.{table_id}"] = schema_fields
                except Exception as e:
                    logger.warning(f"스키마 정보 수집 중 오류: {str(e)}")
            
            # 3. 쿼리 생성 로직
            # 대부분의 경우에는 하나의 주요 테이블을 사용
            main_table = table_matches[0]
            main_table_id = main_table.get("id", "")
            main_dataset_id = main_table.get("dataset_id", "")
            full_table_name = f"`{self.project_id}.{main_dataset_id}.{main_table_id}`"
            
            # 필요한 필드 결정
            fields = field_info.get(f"{main_dataset_id}.{main_table_id}", [])
            
            # 시간 관련 필드 식별
            date_fields = [field.get("name") for field in fields if field.get("type") in ["DATE", "DATETIME", "TIMESTAMP"]]
            
            # 집계 관련 키워드 확인
            count_keywords = ["count", "세기", "개수", "숫자", "횟수"]
            sum_keywords = ["sum", "total", "합계", "합산"]
            avg_keywords = ["average", "avg", "평균"]
            
            has_count = any(keyword in keywords for keyword in count_keywords)
            has_sum = any(keyword in keywords for keyword in sum_keywords)
            has_avg = any(keyword in keywords for keyword in avg_keywords)
            
            # 날짜/기간 관련 키워드 확인
            date_keywords = ["일별", "날짜별", "날짜", "일자", "day", "daily", "per day", "by date"]
            month_keywords = ["월별", "월간", "month", "monthly", "per month", "by month"]
            year_keywords = ["연도별", "연간", "year", "yearly", "annual", "by year"]
            
            has_date_grouping = any(keyword in keywords for keyword in date_keywords)
            has_month_grouping = any(keyword in keywords for keyword in month_keywords)
            has_year_grouping = any(keyword in keywords for keyword in year_keywords)
            
            # 기간 제한 키워드 확인
            recent_keywords = ["recent", "last", "최근"]
            day_period_keywords = ["days", "일간"]
            month_period_keywords = ["months", "개월"]
            year_period_keywords = ["years", "연간"]
            
            # 정렬 관련 키워드 확인
            sort_desc_keywords = ["top", "highest", "most", "상위", "많은"]
            sort_asc_keywords = ["bottom", "lowest", "least", "하위", "적은"]
            
            has_desc_sort = any(keyword in keywords for keyword in sort_desc_keywords)
            has_asc_sort = any(keyword in keywords for keyword in sort_asc_keywords)
            
            # 숫자 추출 (예: "지난 30일")
            import re
            num_matches = re.findall(r'\b(\d+)\s*(?:days|day|months|month|years|year|일|개월|년|주|weeks|week)\b', description)
            period_num = int(num_matches[0]) if num_matches else 30  # 기본값은 30일
            
            # 제한 개수 추출 (예: "상위 10개")
            limit_matches = re.findall(r'\b(?:top|상위|하위)\s*(\d+)\b', description)
            limit_num = int(limit_matches[0]) if limit_matches else 10  # 기본값은 10개
            
            # 쿼리 구성 요소 초기화
            select_clause = []
            from_clause = full_table_name
            where_clause = []
            group_by_clause = []
            order_by_clause = []
            limit_clause = f"LIMIT {limit_num}" if has_desc_sort or has_asc_sort else ""
            
            # 날짜 필드가 있고 최근 데이터를 요청한 경우 WHERE 절 추가
            if date_fields and any(keyword in keywords for keyword in recent_keywords):
                date_field = date_fields[0]  # 첫 번째 날짜 필드 사용
                
                # 기간 유형 결정
                if any(keyword in keywords for keyword in day_period_keywords):
                    where_clause.append(f"{date_field} >= DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} DAY)")
                elif any(keyword in keywords for keyword in month_period_keywords):
                    where_clause.append(f"{date_field} >= DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} MONTH)")
                elif any(keyword in keywords for keyword in year_period_keywords):
                    where_clause.append(f"{date_field} >= DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} YEAR)")
                else:
                    # 기본은 일 단위
                    where_clause.append(f"{date_field} >= DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} DAY)")
            
            # 특별한 경우: GA 테이블 이름에 날짜가 포함된 경우 (_TABLE_SUFFIX 사용)
            ga_pattern = re.compile(r'^ga_.*sessions.*$', re.IGNORECASE)
            if ga_pattern.match(main_table_id):
                # GA 테이블이므로 _TABLE_SUFFIX 사용
                from_clause = f"`{self.project_id}.{main_dataset_id}.{main_table_id.split('_')[0]}_sessions_*`"
                
                if any(keyword in keywords for keyword in recent_keywords):
                    # 기간 유형 결정
                    if any(keyword in keywords for keyword in day_period_keywords):
                        where_clause.append(f"_TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} DAY)) AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())")
                    elif any(keyword in keywords for keyword in month_period_keywords):
                        where_clause.append(f"_TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} MONTH)) AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())")
                    elif any(keyword in keywords for keyword in year_period_keywords):
                        where_clause.append(f"_TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} YEAR)) AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())")
                    else:
                        # 기본은 일 단위
                        where_clause.append(f"_TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {period_num} DAY)) AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())")
            
            # SELECT 및 GROUP BY 절 구성
            numeric_fields = [field.get("name") for field in fields if field.get("type") in ["INTEGER", "FLOAT", "NUMERIC"]]
            
            if has_date_grouping and date_fields:
                date_field = date_fields[0]
                select_clause.append(date_field)
                group_by_clause.append(date_field)
                order_by_clause.append(f"{date_field} ASC")
            elif has_month_grouping and date_fields:
                date_field = date_fields[0]
                select_clause.append(f"FORMAT_DATE('%Y-%m', {date_field}) AS month")
                group_by_clause.append("month")
                order_by_clause.append("month ASC")
            elif has_year_grouping and date_fields:
                date_field = date_fields[0]
                select_clause.append(f"EXTRACT(YEAR FROM {date_field}) AS year")
                group_by_clause.append("year")
                order_by_clause.append("year ASC")
            
            # 집계 함수 추가
            if has_count:
                select_clause.append("COUNT(*) AS count")
                if not order_by_clause and not has_asc_sort:  # 기본 내림차순
                    order_by_clause.append("count DESC")
            
            if has_sum and numeric_fields:
                for i, field in enumerate(numeric_fields[:2]):  # 최대 2개 필드만 합산
                    select_clause.append(f"SUM({field}) AS total_{field}")
                    if i == 0 and not order_by_clause and not has_asc_sort:  # 첫 번째 필드로 정렬
                        order_by_clause.append(f"total_{field} DESC")
            
            if has_avg and numeric_fields:
                for i, field in enumerate(numeric_fields[:2]):  # 최대 2개 필드만 평균
                    select_clause.append(f"AVG({field}) AS avg_{field}")
                    if i == 0 and not order_by_clause and not has_asc_sort:  # 첫 번째 필드로 정렬
                        order_by_clause.append(f"avg_{field} DESC")
            
            # 기본 SELECT 절 (아무것도 선택되지 않은 경우)
            if not select_clause:
                select_clause = ["*"]
                limit_clause = "LIMIT 100"  # 기본 제한
            
            # ORDER BY 절 구성
            if has_asc_sort and order_by_clause:
                # DESC를 ASC로 변경
                order_by_clause = [clause.replace("DESC", "ASC") for clause in order_by_clause]
            
            # 쿼리 조합
            query = f"SELECT {', '.join(select_clause)}\nFROM {from_clause}"
            
            if where_clause:
                query += f"\nWHERE {' AND '.join(where_clause)}"
            
            if group_by_clause:
                query += f"\nGROUP BY {', '.join(group_by_clause)}"
            
            if order_by_clause:
                query += f"\nORDER BY {', '.join(order_by_clause)}"
            
            if limit_clause:
                query += f"\n{limit_clause}"
            
            # 쿼리 및 메타데이터 반환
            return self.success_response({
                "message": "쿼리가 성공적으로 생성되었습니다.",
                "description": description,
                "query": query,
                "used_resources": {
                    "table": f"{main_dataset_id}.{main_table_id}",
                    "fields": select_clause
                },
                "note": "이 쿼리는 자동 생성된 것으로, 실행 전에 검토하고 필요에 따라 수정하세요."
            })
            
        except Exception as e:
            error_message = str(e)
            simplified_message = f"쿼리 생성 중 오류: {error_message[:200]}"
            if len(error_message) > 200:
                simplified_message += "..."
            logger.error(simplified_message)
            return self.fail_response(simplified_message)


if __name__ == "__main__":
    import asyncio
    
    async def test_list_datasets():
        """Test function for the list datasets tool"""
        bq_tool = BigQueryTool()
        result = await bq_tool.list_datasets()
        print(result)
    
    async def test_list_tables():
        """Test function for the list tables tool"""
        bq_tool = BigQueryTool()
        result = await bq_tool.list_tables(dataset_id="analytics_data")
        print(result)
    
    async def test_get_table_schema():
        """Test function for the get table schema tool"""
        bq_tool = BigQueryTool()
        result = await bq_tool.get_table_schema(dataset_id="analytics_data", table_id="ga_sessions_20240101")
        print(result)
    
    async def test_execute_query():
        """Test function for the execute query tool"""
        bq_tool = BigQueryTool()
        query = """
        SELECT date, COUNT(*) as visit_count 
        FROM `analytics_data.ga_sessions_*` 
        WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20240131'
        GROUP BY date 
        ORDER BY date
        LIMIT 100
        """
        result = await bq_tool.execute_query(query=query, max_results=100)
        print(result)
        
    async def test_search_resources():
        """Test function for the search resources tool"""
        bq_tool = BigQueryTool()
        result = await bq_tool.search_resources(keywords="user sessions website visits")
        print(result)
        
    async def test_generate_query():
        """Test function for the generate query tool"""
        bq_tool = BigQueryTool()
        result = await bq_tool.generate_query(
            description="지난 30일간 일별 방문자 수 집계",
            dataset_hint="analytics_data",
            table_hint="ga_sessions"
        )
        print(result)
    
    async def run_tests():
        """Run all test functions"""
        await test_list_datasets()
        await test_list_tables()
        await test_get_table_schema()
        await test_execute_query()
        await test_search_resources()
        await test_generate_query()
        
    asyncio.run(run_tests())