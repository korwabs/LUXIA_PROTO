import traceback
import json

from agentpress.tool import ToolResult, openapi_schema, xml_schema
from agentpress.thread_manager import ThreadManager
from sandbox.sandbox import SandboxToolsBase, Sandbox
from utils.logger import logger


class SandboxBrowserTool(SandboxToolsBase):
    """Tool for executing tasks in a Daytona sandbox with browser-use capabilities."""
    
    def __init__(self, project_id: str, thread_id: str, thread_manager: ThreadManager):
        super().__init__(project_id, thread_manager)
        self.thread_id = thread_id

    async def _execute_browser_action(self, endpoint: str, params: dict = None, method: str = "POST") -> ToolResult:
        """Execute a browser automation action through the API
        
        Args:
            endpoint (str): The API endpoint to call
            params (dict, optional): Parameters to send. Defaults to None.
            method (str, optional): HTTP method to use. Defaults to "POST".
            
        Returns:
            ToolResult: Result of the execution
        """
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Build the curl command
            url = f"http://localhost:8002/api/automation/{endpoint}"
            
            if method == "GET" and params:
                query_params = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}?{query_params}"
                curl_cmd = f"curl -s -X {method} '{url}' -H 'Content-Type: application/json'"
            else:
                curl_cmd = f"curl -s -X {method} '{url}' -H 'Content-Type: application/json'"
                if params:
                    json_data = json.dumps(params)
                    curl_cmd += f" -d '{json_data}'"
            
            logger.debug("\033[95mExecuting curl command:\033[0m")
            logger.debug(f"{curl_cmd}")
            
            response = self.sandbox.process.exec(curl_cmd, timeout=30)
            
            if response.exit_code == 0:
                try:
                    result = json.loads(response.result)

                    if not "content" in result:
                        result["content"] = ""
                    
                    if not "role" in result:
                        result["role"] = "assistant"

                    logger.info("Browser automation request completed successfully")

                    # Add full result to thread messages for state tracking
                    added_message = await self.thread_manager.add_message(
                        thread_id=self.thread_id,
                        type="browser_state",
                        content=result,
                        is_llm_message=False
                    )

                    # Return tool-specific success response
                    success_response = {
                        "success": True,
                        "message": result.get("message", "Browser action completed successfully")
                    }

                    # Add message ID if available
                    if added_message and 'message_id' in added_message:
                        success_response['message_id'] = added_message['message_id']

                    # Add relevant browser-specific info
                    if result.get("url"):
                        success_response["url"] = result["url"]
                    if result.get("title"):
                        success_response["title"] = result["title"]
                    if result.get("element_count"):
                        success_response["elements_found"] = result["element_count"]
                    if result.get("pixels_below"):
                        success_response["scrollable_content"] = result["pixels_below"] > 0
                    # Add OCR text when available
                    if result.get("ocr_text"):
                        success_response["ocr_text"] = result["ocr_text"]

                    return self.success_response(success_response)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response JSON: {response.result} {e}")
                    return self.fail_response(f"Failed to parse response JSON: {response.result} {e}")
            else:
                logger.error(f"Browser automation request failed 2: {response}")
                return self.fail_response(f"Browser automation request failed 2: {response}")

        except Exception as e:
            logger.error(f"Error executing browser action: {e}")
            logger.debug(traceback.format_exc())
            return self.fail_response(f"Error executing browser action: {e}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_navigate_to",
            "description": "Navigate to a specific url",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The url to navigate to"
                    }
                },
                "required": ["url"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-navigate-to",
        mappings=[
            {"param_name": "url", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-navigate-to>
        https://example.com
        </browser-navigate-to>
        '''
    )
    async def browser_navigate_to(self, url: str) -> ToolResult:
        """Navigate to a specific url
        
        Args:
            url (str): The url to navigate to
            
        Returns:
            dict: Result of the execution
        """
        return await self._execute_browser_action("navigate_to", {"url": url})

    # @openapi_schema({
    #     "type": "function",
    #     "function": {
    #         "name": "browser_search_google",
    #         "description": "Search Google with the provided query",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "query": {
    #                     "type": "string",
    #                     "description": "The search query to use"
    #                 }
    #             },
    #             "required": ["query"]
    #         }
    #     }
    # })
    # @xml_schema(
    #     tag_name="browser-search-google",
    #     mappings=[
    #         {"param_name": "query", "node_type": "content", "path": "."}
    #     ],
    #     example='''
    #     <browser-search-google>
    #     artificial intelligence news
    #     </browser-search-google>
    #     '''
    # )
    # async def browser_search_google(self, query: str) -> ToolResult:
    #     """Search Google with the provided query
        
    #     Args:
    #         query (str): The search query to use
            
    #     Returns:
    #         dict: Result of the execution
    #     """
    #     logger.debug(f"\033[95mSearching Google for: {query}\033[0m")
    #     return await self._execute_browser_action("search_google", {"query": query})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_go_back",
            "description": "Navigate back in browser history",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    })
    @xml_schema(
        tag_name="browser-go-back",
        mappings=[],
        example='''
        <browser-go-back></browser-go-back>
        '''
    )
    async def browser_go_back(self) -> ToolResult:
        """Navigate back in browser history
        
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mNavigating back in browser history\033[0m")
        return await self._execute_browser_action("go_back", {})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_wait",
            "description": "Wait for the specified number of seconds",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Number of seconds to wait (default: 3)"
                    }
                }
            }
        }
    })
    @xml_schema(
        tag_name="browser-wait",
        mappings=[
            {"param_name": "seconds", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-wait>
        5
        </browser-wait>
        '''
    )
    async def browser_wait(self, seconds: int = 3) -> ToolResult:
        """Wait for the specified number of seconds
        
        Args:
            seconds (int, optional): Number of seconds to wait. Defaults to 3.
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mWaiting for {seconds} seconds\033[0m")
        return await self._execute_browser_action("wait", {"seconds": seconds})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_click_element",
            "description": "Click on an element by index",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The index of the element to click"
                    }
                },
                "required": ["index"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-click-element",
        mappings=[
            {"param_name": "index", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-click-element>
        2
        </browser-click-element>
        '''
    )
    async def browser_click_element(self, index: int) -> ToolResult:
        """Click on an element by index
        
        Args:
            index (int): The index of the element to click
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mClicking element with index: {index}\033[0m")
        return await self._execute_browser_action("click_element", {"index": index})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_input_text",
            "description": "Input text into an element",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The index of the element to input text into"
                    },
                    "text": {
                        "type": "string",
                        "description": "The text to input"
                    }
                },
                "required": ["index", "text"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-input-text",
        mappings=[
            {"param_name": "index", "node_type": "attribute", "path": "."},
            {"param_name": "text", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-input-text index="2">
        Hello, world!
        </browser-input-text>
        '''
    )
    async def browser_input_text(self, index: int, text: str) -> ToolResult:
        """Input text into an element
        
        Args:
            index (int): The index of the element to input text into
            text (str): The text to input
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mInputting text into element {index}: {text}\033[0m")
        return await self._execute_browser_action("input_text", {"index": index, "text": text})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_send_keys",
            "description": "Send keyboard keys such as Enter, Escape, or keyboard shortcuts",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "The keys to send (e.g., 'Enter', 'Escape', 'Control+a')"
                    }
                },
                "required": ["keys"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-send-keys",
        mappings=[
            {"param_name": "keys", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-send-keys>
        Enter
        </browser-send-keys>
        '''
    )
    async def browser_send_keys(self, keys: str) -> ToolResult:
        """Send keyboard keys
        
        Args:
            keys (str): The keys to send (e.g., 'Enter', 'Escape', 'Control+a')
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mSending keys: {keys}\033[0m")
        return await self._execute_browser_action("send_keys", {"keys": keys})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_switch_tab",
            "description": "Switch to a different browser tab",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "integer",
                        "description": "The ID of the tab to switch to"
                    }
                },
                "required": ["page_id"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-switch-tab",
        mappings=[
            {"param_name": "page_id", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-switch-tab>
        1
        </browser-switch-tab>
        '''
    )
    async def browser_switch_tab(self, page_id: int) -> ToolResult:
        """Switch to a different browser tab
        
        Args:
            page_id (int): The ID of the tab to switch to
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mSwitching to tab: {page_id}\033[0m")
        return await self._execute_browser_action("switch_tab", {"page_id": page_id})

    # @openapi_schema({
    #     "type": "function",
    #     "function": {
    #         "name": "browser_open_tab",
    #         "description": "Open a new browser tab with the specified URL",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "url": {
    #                     "type": "string",
    #                     "description": "The URL to open in the new tab"
    #                 }
    #             },
    #             "required": ["url"]
    #         }
    #     }
    # })
    # @xml_schema(
    #     tag_name="browser-open-tab",
    #     mappings=[
    #         {"param_name": "url", "node_type": "content", "path": "."}
    #     ],
    #     example='''
    #     <browser-open-tab>
    #     https://example.com
    #     </browser-open-tab>
    #     '''
    # )
    # async def browser_open_tab(self, url: str) -> ToolResult:
    #     """Open a new browser tab with the specified URL
        
    #     Args:
    #         url (str): The URL to open in the new tab
            
    #     Returns:
    #         dict: Result of the execution
    #     """
    #     logger.debug(f"\033[95mOpening new tab with URL: {url}\033[0m")
    #     return await self._execute_browser_action("open_tab", {"url": url})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_close_tab",
            "description": "Close a browser tab",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "integer",
                        "description": "The ID of the tab to close"
                    }
                },
                "required": ["page_id"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-close-tab",
        mappings=[
            {"param_name": "page_id", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-close-tab>
        1
        </browser-close-tab>
        '''
    )
    async def browser_close_tab(self, page_id: int) -> ToolResult:
        """Close a browser tab
        
        Args:
            page_id (int): The ID of the tab to close
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mClosing tab: {page_id}\033[0m")
        return await self._execute_browser_action("close_tab", {"page_id": page_id})

    # @openapi_schema({
    #     "type": "function",
    #     "function": {
    #         "name": "browser_extract_content",
    #         "description": "Extract content from the current page based on the provided goal",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "goal": {
    #                     "type": "string",
    #                     "description": "The extraction goal (e.g., 'extract all links', 'find product information')"
    #                 }
    #             },
    #             "required": ["goal"]
    #         }
    #     }
    # })
    # @xml_schema(
    #     tag_name="browser-extract-content",
    #     mappings=[
    #         {"param_name": "goal", "node_type": "content", "path": "."}
    #     ],
    #     example='''
    #     <browser-extract-content>
    #     Extract all links on the page
    #     </browser-extract-content>
    #     '''
    # )
    # async def browser_extract_content(self, goal: str) -> ToolResult:
    #     """Extract content from the current page based on the provided goal
        
    #     Args:
    #         goal (str): The extraction goal
            
    #     Returns:
    #         dict: Result of the execution
    #     """
    #     logger.debug(f"\033[95mExtracting content with goal: {goal}\033[0m")
    #     result = await self._execute_browser_action("extract_content", {"goal": goal})
        
    #     # Format content for better readability
    #     if result.get("success"):
    #         logger.debug(f"\033[92mContent extraction successful\033[0m")
    #         content = result.data.get("content", "")
    #         url = result.data.get("url", "")
    #         title = result.data.get("title", "")
            
    #         if content:
    #             content_preview = content[:200] + "..." if len(content) > 200 else content
    #             logger.debug(f"\033[95mExtracted content from {title} ({url}):\033[0m")
    #             logger.debug(f"\033[96m{content_preview}\033[0m")
    #             logger.debug(f"\033[95mTotal content length: {len(content)} characters\033[0m")
    #         else:
    #             logger.debug(f"\033[93mNo content extracted from {url}\033[0m")
    #     else:
    #         logger.debug(f"\033[91mFailed to extract content: {result.data.get('error', 'Unknown error')}\033[0m")
        
    #     return result

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_scroll_down",
            "description": "Scroll down the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "Pixel amount to scroll (if not specified, scrolls one page)"
                    }
                }
            }
        }
    })
    @xml_schema(
        tag_name="browser-scroll-down",
        mappings=[
            {"param_name": "amount", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-scroll-down>
        500
        </browser-scroll-down>
        '''
    )
    async def browser_scroll_down(self, amount: int = None) -> ToolResult:
        """Scroll down the page
        
        Args:
            amount (int, optional): Pixel amount to scroll. If None, scrolls one page.
            
        Returns:
            dict: Result of the execution
        """
        params = {}
        if amount is not None:
            params["amount"] = amount
            logger.debug(f"\033[95mScrolling down by {amount} pixels\033[0m")
        else:
            logger.debug(f"\033[95mScrolling down one page\033[0m")
        
        return await self._execute_browser_action("scroll_down", params)

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_scroll_up",
            "description": "Scroll up the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "Pixel amount to scroll (if not specified, scrolls one page)"
                    }
                }
            }
        }
    })
    @xml_schema(
        tag_name="browser-scroll-up",
        mappings=[
            {"param_name": "amount", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-scroll-up>
        500
        </browser-scroll-up>
        '''
    )
    async def browser_scroll_up(self, amount: int = None) -> ToolResult:
        """Scroll up the page
        
        Args:
            amount (int, optional): Pixel amount to scroll. If None, scrolls one page.
            
        Returns:
            dict: Result of the execution
        """
        params = {}
        if amount is not None:
            params["amount"] = amount
            logger.debug(f"\033[95mScrolling up by {amount} pixels\033[0m")
        else:
            logger.debug(f"\033[95mScrolling up one page\033[0m")
        
        return await self._execute_browser_action("scroll_up", params)

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_scroll_to_text",
            "description": "Scroll to specific text on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to scroll to"
                    }
                },
                "required": ["text"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-scroll-to-text",
        mappings=[
            {"param_name": "text", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-scroll-to-text>
        Contact Us
        </browser-scroll-to-text>
        '''
    )
    async def browser_scroll_to_text(self, text: str) -> ToolResult:
        """Scroll to specific text on the page
        
        Args:
            text (str): The text to scroll to
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mScrolling to text: {text}\033[0m")
        return await self._execute_browser_action("scroll_to_text", {"text": text})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_get_dropdown_options",
            "description": "Get all options from a dropdown element",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The index of the dropdown element"
                    }
                },
                "required": ["index"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-get-dropdown-options",
        mappings=[
            {"param_name": "index", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-get-dropdown-options>
        2
        </browser-get-dropdown-options>
        '''
    )
    async def browser_get_dropdown_options(self, index: int) -> ToolResult:
        """Get all options from a dropdown element
        
        Args:
            index (int): The index of the dropdown element
            
        Returns:
            dict: Result of the execution with the dropdown options
        """
        logger.debug(f"\033[95mGetting options from dropdown with index: {index}\033[0m")
        return await self._execute_browser_action("get_dropdown_options", {"index": index})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_select_dropdown_option",
            "description": "Select an option from a dropdown by text",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The index of the dropdown element"
                    },
                    "text": {
                        "type": "string",
                        "description": "The text of the option to select"
                    }
                },
                "required": ["index", "text"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-select-dropdown-option",
        mappings=[
            {"param_name": "index", "node_type": "attribute", "path": "."},
            {"param_name": "text", "node_type": "content", "path": "."}
        ],
        example='''
        <browser-select-dropdown-option index="2">
        Option 1
        </browser-select-dropdown-option>
        '''
    )
    async def browser_select_dropdown_option(self, index: int, text: str) -> ToolResult:
        """Select an option from a dropdown by text
        
        Args:
            index (int): The index of the dropdown element
            text (str): The text of the option to select
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mSelecting option '{text}' from dropdown with index: {index}\033[0m")
        return await self._execute_browser_action("select_dropdown_option", {"index": index, "text": text})

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_drag_drop",
            "description": "Perform drag and drop operation between elements or coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_source": {
                        "type": "string",
                        "description": "The source element selector"
                    },
                    "element_target": {
                        "type": "string",
                        "description": "The target element selector"
                    },
                    "coord_source_x": {
                        "type": "integer",
                        "description": "The source X coordinate"
                    },
                    "coord_source_y": {
                        "type": "integer",
                        "description": "The source Y coordinate"
                    },
                    "coord_target_x": {
                        "type": "integer",
                        "description": "The target X coordinate"
                    },
                    "coord_target_y": {
                        "type": "integer",
                        "description": "The target Y coordinate"
                    }
                }
            }
        }
    })
    @xml_schema(
        tag_name="browser-drag-drop",
        mappings=[
            {"param_name": "element_source", "node_type": "attribute", "path": "."},
            {"param_name": "element_target", "node_type": "attribute", "path": "."},
            {"param_name": "coord_source_x", "node_type": "attribute", "path": "."},
            {"param_name": "coord_source_y", "node_type": "attribute", "path": "."},
            {"param_name": "coord_target_x", "node_type": "attribute", "path": "."},
            {"param_name": "coord_target_y", "node_type": "attribute", "path": "."}
        ],
        example='''
        <browser-drag-drop element_source="#draggable" element_target="#droppable"></browser-drag-drop>
        '''
    )
    async def browser_drag_drop(self, element_source: str = None, element_target: str = None, 
                               coord_source_x: int = None, coord_source_y: int = None,
                               coord_target_x: int = None, coord_target_y: int = None) -> ToolResult:
        """Perform drag and drop operation between elements or coordinates
        
        Args:
            element_source (str, optional): The source element selector
            element_target (str, optional): The target element selector
            coord_source_x (int, optional): The source X coordinate
            coord_source_y (int, optional): The source Y coordinate
            coord_target_x (int, optional): The target X coordinate
            coord_target_y (int, optional): The target Y coordinate
            
        Returns:
            dict: Result of the execution
        """
        params = {}
        
        if element_source and element_target:
            params["element_source"] = element_source
            params["element_target"] = element_target
            logger.debug(f"\033[95mDragging from element '{element_source}' to '{element_target}'\033[0m")
        elif all(coord is not None for coord in [coord_source_x, coord_source_y, coord_target_x, coord_target_y]):
            params["coord_source_x"] = coord_source_x
            params["coord_source_y"] = coord_source_y
            params["coord_target_x"] = coord_target_x
            params["coord_target_y"] = coord_target_y
            logger.debug(f"\033[95mDragging from coordinates ({coord_source_x}, {coord_source_y}) to ({coord_target_x}, {coord_target_y})\033[0m")
        else:
            return self.fail_response("Must provide either element selectors or coordinates for drag and drop")
        
        return await self._execute_browser_action("drag_drop", params)

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser_click_coordinates",
            "description": "Click at specific X,Y coordinates on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "The X coordinate to click"
                    },
                    "y": {
                        "type": "integer",
                        "description": "The Y coordinate to click"
                    }
                },
                "required": ["x", "y"]
            }
        }
    })
    @xml_schema(
        tag_name="browser-click-coordinates",
        mappings=[
            {"param_name": "x", "node_type": "attribute", "path": "."},
            {"param_name": "y", "node_type": "attribute", "path": "."}
        ],
        example='''
        <browser-click-coordinates x="100" y="200"></browser-click-coordinates>
        '''
    )
    async def browser_click_coordinates(self, x: int, y: int) -> ToolResult:
        """Click at specific X,Y coordinates on the page
        
        Args:
            x (int): The X coordinate to click
            y (int): The Y coordinate to click
            
        Returns:
            dict: Result of the execution
        """
        logger.debug(f"\033[95mClicking at coordinates: ({x}, {y})\033[0m")
        return await self._execute_browser_action("click_coordinates", {"x": x, "y": y})

    async def browser_scroll_to_text(self, text, timeout=5000):
        """
        텍스트가 포함된 요소로 스크롤합니다.
        
        Args:
            text (str): 찾을 텍스트
            timeout (int): 최대 대기 시간(ms)
            
        Returns:
            dict: 작업 결과
        """
        try:
            # 페이지에서 텍스트 검색 및 스크롤 수행
            result = await self.browser.evaluate_async(f"""
                async () => {{
                    const findTextInPage = (text) => {{
                        const walker = document.createTreeWalker(
                            document.body, NodeFilter.SHOW_TEXT, null, false
                        );
                        let node;
                        while (node = walker.nextNode()) {{
                            if (node.textContent.includes(text)) {{
                                return node.parentElement;
                            }}
                        }}
                        return null;
                    }};
                    
                    const element = findTextInPage("{text}");
                    if (element) {{
                        element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        return {{ success: true, message: "텍스트 요소로 스크롤 성공" }};
                    }}
                    return {{ success: false, message: "텍스트를 찾을 수 없음" }};
                }}
            """, timeout=timeout)
            
            return result or {"success": False, "message": "텍스트 스크롤 실패"}
        except Exception as e:
            return {"success": False, "message": f"텍스트 스크롤 오류: {str(e)}"}
    
    async def browser_login(self, url, username_selector, password_selector, 
                           submit_selector, username, password, 
                           cookie_accept_selector=None, wait_after_login=5000):
        """
        웹사이트에 로그인합니다.
        
        Args:
            url (str): 로그인 페이지 URL
            username_selector (str): 사용자명/이메일 입력 필드 선택자
            password_selector (str): 비밀번호 입력 필드 선택자
            submit_selector (str): 로그인 폼 제출 버튼 선택자
            username (str): 사용자명/이메일
            password (str): 비밀번호
            cookie_accept_selector (str, optional): 쿠키 동의 버튼 선택자
            wait_after_login (int): 로그인 후 대기 시간(ms)
            
        Returns:
            dict: 로그인 결과
        """
        try:
            # 1. 페이지 탐색
            navigate_result = await self.browser_navigate({"url": url})
            if not navigate_result.get("success", False):
                return {"success": False, "message": "로그인 페이지 탐색 실패"}
            
            # 2. 페이지 로드 대기
            await self.browser_wait(3)
            
            # 3. 쿠키 동의 처리 (선택적)
            if cookie_accept_selector:
                try:
                    cookie_element = await self.browser.wait_for_selector(cookie_accept_selector, timeout=5000)
                    if cookie_element:
                        await cookie_element.click()
                        await self.browser_wait(1)
                except:
                    # 쿠키 동의 요소가 없어도 계속 진행
                    pass
            
            # 4. 사용자명 입력
            try:
                username_element = await self.browser.wait_for_selector(username_selector, timeout=5000)
                if username_element:
                    await username_element.fill(username)
                else:
                    return {"success": False, "message": "사용자명 입력 필드를 찾을 수 없음"}
            except Exception as e:
                return {"success": False, "message": f"사용자명 입력 오류: {str(e)}"}
            
            # 5. 비밀번호 입력
            try:
                password_element = await self.browser.wait_for_selector(password_selector, timeout=5000)
                if password_element:
                    await password_element.fill(password)
                else:
                    return {"success": False, "message": "비밀번호 입력 필드를 찾을 수 없음"}
            except Exception as e:
                return {"success": False, "message": f"비밀번호 입력 오류: {str(e)}"}
            
            # 6. 로그인 버튼 클릭
            try:
                submit_element = await self.browser.wait_for_selector(submit_selector, timeout=5000)
                if submit_element:
                    await submit_element.click()
                else:
                    return {"success": False, "message": "로그인 버튼을 찾을 수 없음"}
            except Exception as e:
                return {"success": False, "message": f"로그인 버튼 클릭 오류: {str(e)}"}
            
            # 7. 로그인 후 대기
            await self.browser_wait(wait_after_login / 1000)  # 초 단위로 변환
            
            # 8. 로그인 성공 확인 (URL 변경 또는 특정 요소 존재 여부)
            current_url = await self.browser.evaluate("() => window.location.href")
            
            # 로그인 페이지에 머물러 있는지 확인 (실패 케이스)
            if current_url == url:
                # 오류 메시지 확인
                error_text = await self.browser.evaluate("""
                    () => {
                        const errorElements = document.querySelectorAll('.error, .alert, .message');
                        for (const el of errorElements) {
                            if (el.textContent.includes('로그인') || 
                                el.textContent.includes('login') || 
                                el.textContent.includes('password')) {
                                return el.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                
                if error_text:
                    return {"success": False, "message": f"로그인 실패: {error_text}"}
                
                return {"success": False, "message": "로그인이 성공적으로 완료되지 않았습니다."}
            
            return {"success": True, "message": "로그인 성공", "current_url": current_url}
            
        except Exception as e:
            return {"success": False, "message": f"로그인 프로세스 오류: {str(e)}"}
    
    async def browser_navigate_to_mypage(self, mypage_link_selector=None, mypage_text=None):
        """
        마이페이지로 이동합니다.
        
        Args:
            mypage_link_selector (str, optional): 마이페이지 링크 선택자
            mypage_text (str, optional): 마이페이지 링크 텍스트 (선택자가 없을 경우 사용)
            
        Returns:
            dict: 이동 결과
        """
        try:
            # 선택자로 마이페이지 찾기
            if mypage_link_selector:
                try:
                    mypage_element = await self.browser.wait_for_selector(mypage_link_selector, timeout=5000)
                    if mypage_element:
                        await mypage_element.click()
                        await self.browser_wait(3)
                        current_url = await self.browser.evaluate("() => window.location.href")
                        return {"success": True, "message": "마이페이지 이동 성공", "url": current_url}
                except Exception as e:
                    return {"success": False, "message": f"마이페이지 선택자로 이동 실패: {str(e)}"}
            
            # 텍스트로 마이페이지 찾기
            if mypage_text:
                scroll_result = await self.browser_scroll_to_text(mypage_text)
                if scroll_result.get("success", False):
                    # 텍스트가 포함된 링크 찾기
                    click_result = await self.browser.evaluate_async(f"""
                        async () => {{
                            const findLinkWithText = (text) => {{
                                const links = Array.from(document.querySelectorAll('a'));
                                return links.find(link => link.textContent.includes(text));
                            }};
                            
                            const link = findLinkWithText("{mypage_text}");
                            if (link) {{
                                link.click();
                                return {{ success: true, message: "마이페이지 링크 클릭 성공" }};
                            }}
                            return {{ success: false, message: "마이페이지 링크를 찾을 수 없음" }};
                        }}
                    """)
                    
                    if click_result.get("success", False):
                        await self.browser_wait(3)
                        current_url = await self.browser.evaluate("() => window.location.href")
                        return {"success": True, "message": "마이페이지 이동 성공", "url": current_url}
            
            # 일반적인 마이페이지 링크 패턴 시도
            common_patterns = [
                'a[href*="account"]', 'a[href*="mypage"]', 'a[href*="profile"]',
                'a[href*="my-page"]', 'a[href*="my-account"]', 'a[href*="user"]'
            ]
            
            for pattern in common_patterns:
                try:
                    element = await self.browser.query_selector(pattern)
                    if element:
                        await element.click()
                        await self.browser_wait(3)
                        current_url = await self.browser.evaluate("() => window.location.href")
                        return {"success": True, "message": f"패턴({pattern})으로 마이페이지 이동 성공", "url": current_url}
                except:
                    continue
            
            return {"success": False, "message": "마이페이지를 찾을 수 없음"}
            
        except Exception as e:
            return {"success": False, "message": f"마이페이지 이동 오류: {str(e)}"}
    
    async def browser_analyze_page_structure(self):
        """
        현재 페이지의 구조를 분석합니다.
        
        Returns:
            dict: 페이지 구조 분석 결과
        """
        try:
            page_structure = await self.browser.evaluate_async("""
                async () => {
                    // 페이지 타이틀
                    const pageTitle = document.title;
                    
                    // 헤딩 요소 추출
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
                        .map(h => ({
                            tag: h.tagName.toLowerCase(),
                            text: h.textContent.trim(),
                            visible: h.getBoundingClientRect().height > 0
                        }))
                        .filter(h => h.text && h.visible);
                    
                    // 주요 섹션 식별
                    const sections = Array.from(document.querySelectorAll('section, div[class*="section"], div[id*="section"]'))
                        .map(section => {
                            const heading = section.querySelector('h1, h2, h3, h4, h5, h6');
                            return {
                                id: section.id || null,
                                className: section.className,
                                headingText: heading ? heading.textContent.trim() : null,
                                childrenCount: section.children.length
                            };
                        });
                    
                    // 폼 요소 분석
                    const forms = Array.from(document.querySelectorAll('form'))
                        .map(form => {
                            const inputs = Array.from(form.querySelectorAll('input, select, textarea'))
                                .map(input => ({
                                    type: input.type || input.tagName.toLowerCase(),
                                    name: input.name || null,
                                    id: input.id || null,
                                    placeholder: input.placeholder || null
                                }));
                            
                            const buttons = Array.from(form.querySelectorAll('button, input[type="submit"]'))
                                .map(button => ({
                                    text: button.textContent.trim() || button.value,
                                    type: button.type || 'button'
                                }));
                            
                            return {
                                id: form.id || null,
                                action: form.action || null,
                                method: form.method || 'get',
                                inputs,
                                buttons
                            };
                        });
                    
                    // 네비게이션 메뉴 분석
                    const navElements = Array.from(document.querySelectorAll('nav, .nav, .menu, .navigation, header ul'))
                        .map(nav => {
                            const links = Array.from(nav.querySelectorAll('a'))
                                .map(a => ({
                                    text: a.textContent.trim(),
                                    href: a.href,
                                    current: a.getAttribute('aria-current') === 'page' || 
                                            a.classList.contains('active') || 
                                            a.classList.contains('current')
                                }))
                                .filter(link => link.text);
                            
                            return { links };
                        });
                    
                    // 버튼 및 액션 요소 분석
                    const actionElements = Array.from(document.querySelectorAll('button, a.btn, .button, [role="button"]'))
                        .map(el => ({
                            text: el.textContent.trim(),
                            type: el.tagName.toLowerCase(),
                            id: el.id || null,
                            className: el.className
                        }))
                        .filter(btn => btn.text);
                    
                    return {
                        pageTitle,
                        headings,
                        sections,
                        forms,
                        navigation: navElements,
                        actionElements,
                        url: window.location.href,
                        pageMetadata: {
                            description: document.querySelector('meta[name="description"]')?.content || null,
                            keywords: document.querySelector('meta[name="keywords"]')?.content || null
                        }
                    };
                }
            """)
            
            return {"success": True, "message": "페이지 구조 분석 성공", "structure": page_structure}
            
        except Exception as e:
            return {"success": False, "message": f"페이지 구조 분석 오류: {str(e)}"}
    
    async def browser_extract_ui_metrics(self):
        """
        UI 지표를 추출합니다.
        
        Returns:
            dict: UI 지표 추출 결과
        """
        try:
            ui_metrics = await self.browser.evaluate_async("""
                async () => {
                    // 요소 수
                    const elementCount = document.querySelectorAll('*').length;
                    
                    // 이미지 분석
                    const images = Array.from(document.querySelectorAll('img'));
                    const imageMetrics = {
                        total: images.length,
                        withoutAlt: images.filter(img => !img.alt).length,
                        lazy: images.filter(img => img.loading === 'lazy').length
                    };
                    
                    // 대비 검사 (W3C 권장사항)
                    const contrastCheck = () => {
                        const textElements = Array.from(document.querySelectorAll('p, span, h1, h2, h3, h4, h5, h6, a, button'));
                        let lowContrastCount = 0;
                        
                        textElements.forEach(el => {
                            const style = window.getComputedStyle(el);
                            const textColor = style.color;
                            const bgColor = style.backgroundColor;
                            
                            // 단순화된 대비 검사 (정확한 검사는 더 복잡한 알고리즘 필요)
                            if (textColor && bgColor && textColor === bgColor) {
                                lowContrastCount++;
                            }
                        });
                        
                        return {
                            textElementsCount: textElements.length,
                            potentialLowContrastCount: lowContrastCount
                        };
                    };
                    
                    // 로드 시간 측정 (대략적)
                    const performanceMetrics = (() => {
                        if (window.performance && window.performance.timing) {
                            const timing = window.performance.timing;
                            const loadTime = timing.loadEventEnd - timing.navigationStart;
                            const domReadyTime = timing.domComplete - timing.domLoading;
                            
                            return {
                                loadTimeMs: loadTime,
                                domReadyTimeMs: domReadyTime
                            };
                        }
                        return null;
                    })();
                    
                    // 페이지 크기 및 스크롤 분석
                    const pageMetrics = {
                        windowHeight: window.innerHeight,
                        windowWidth: window.innerWidth,
                        documentHeight: document.documentElement.scrollHeight,
                        documentWidth: document.documentElement.scrollWidth,
                        scrollRatio: document.documentElement.scrollHeight / window.innerHeight
                    };
                    
                    // 클릭 가능 요소 접근성
                    const clickableElements = Array.from(document.querySelectorAll('a, button, [role="button"], input[type="submit"]'));
                    const clickableMetrics = {
                        total: clickableElements.length,
                        smallTargets: clickableElements.filter(el => {
                            const rect = el.getBoundingClientRect();
                            return (rect.width < 44 || rect.height < 44); // WCAG 권장 최소 크기
                        }).length,
                        withoutLabels: clickableElements.filter(el => {
                            return !el.textContent.trim() && !el.getAttribute('aria-label') && !el.getAttribute('title');
                        }).length
                    };
                    
                    return {
                        elementCount,
                        imageMetrics,
                        contrastIssues: contrastCheck(),
                        performance: performanceMetrics,
                        pageMetrics,
                        clickableMetrics
                    };
                }
            """)
            
            return {"success": True, "message": "UI 지표 추출 성공", "metrics": ui_metrics}
            
        except Exception as e:
            return {"success": False, "message": f"UI 지표 추출 오류: {str(e)}"}
    
    async def browser_capture_full_page_screenshot(self, output_path=None):
        """
        전체 페이지 스크린샷을 캡처합니다.
        
        Args:
            output_path (str, optional): 스크린샷 저장 경로
            
        Returns:
            dict: 캡처 결과
        """
        try:
            # 페이지 전체 크기 측정
            page_dimensions = await self.browser.evaluate("""
                () => ({
                    width: document.documentElement.scrollWidth,
                    height: document.documentElement.scrollHeight
                })
            """)
            
            # 브라우저 뷰포트 크기 설정
            await self.browser.set_viewport_size({
                'width': page_dimensions['width'],
                'height': page_dimensions['height']
            })
            
            # 스크린샷 촬영
            if output_path:
                await self.browser.screenshot(path=output_path, full_page=True)
                screenshot_data = None
                file_path = output_path
            else:
                # 파일로 저장하지 않고 바이너리 데이터로 반환
                screenshot_binary = await self.browser.screenshot(full_page=True)
                screenshot_data = base64.b64encode(screenshot_binary).decode('utf-8')
                file_path = None
            
            # 원래 뷰포트 크기로 복원 (기본값)
            await self.browser.set_viewport_size({'width': 1280, 'height': 720})
            
            return {
                "success": True, 
                "message": "전체 페이지 스크린샷 캡처 성공", 
                "file_path": file_path,
                "data": screenshot_data,
                "dimensions": page_dimensions
            }
            
        except Exception as e:
            return {"success": False, "message": f"전체 페이지 스크린샷 캡처 오류: {str(e)}"}
    
    async def browser_run_a11y_audit(self):
        """
        접근성 감사를 실행합니다.
        
        Returns:
            dict: 접근성 감사 결과
        """
        try:
            # axe-core 라이브러리 주입 (접근성 테스트 라이브러리)
            await self.browser.add_script_tag({
                'url': 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.4.1/axe.min.js'
            })
            
            # 접근성 감사 실행
            a11y_results = await self.browser.evaluate_async("""
                async () => {
                    // axe가 로드되었는지 확인
                    if (typeof axe === 'undefined') {
                        return { error: 'axe-core 라이브러리를 로드할 수 없습니다.' };
                    }
                    
                    try {
                        // axe 실행
                        const results = await axe.run();
                        
                        // 결과 요약
                        const summary = {
                            violations: results.violations.length,
                            incomplete: results.incomplete.length,
                            inapplicable: results.inapplicable.length,
                            passes: results.passes.length
                        };
                        
                        // 주요 위반 사항 추출
                        const mainViolations = results.violations.map(violation => ({
                            id: violation.id,
                            impact: violation.impact,
                            description: violation.description,
                            help: violation.help,
                            helpUrl: violation.helpUrl,
                            nodes: violation.nodes.length
                        }));
                        
                        return {
                            summary,
                            mainViolations,
                            url: window.location.href
                        };
                    } catch (error) {
                        return { error: error.toString() };
                    }
                }
            """)
            
            return {"success": True, "message": "접근성 감사 성공", "results": a11y_results}
            
        except Exception as e:
            return {"success": False, "message": f"접근성 감사 오류: {str(e)}"}
