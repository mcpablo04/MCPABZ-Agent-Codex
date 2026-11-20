"""
MCP (Model Context Protocol) Client

Connects to local MCP servers via stdio transport and exposes their tools
to the coding agent. Implements the essential JSON-RPC protocol needed for
tool discovery and execution.
"""
import json
import subprocess
import sys
import threading
import time
import queue
from pathlib import Path
from typing import Any, Dict, List, Optional


class MCPServer:
    """Configuration for an MCP server."""
    def __init__(self, name: str, command: str, args: List[str] = None, description: str = ""):
        self.name = name
        self.command = command
        self.args = args or []
        self.description = description
        self.is_running = False
        self.tools: List[Dict[str, Any]] = []
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._message_queue: queue.Queue = queue.Queue()
        self._request_id = 0
        self._pending = {}
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the MCP server process."""
        with self._lock:
            if self.is_running:
                return True
            
            try:
                # Use CREATE_NO_WINDOW on Windows to prevent console windows
                creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                self.process = subprocess.Popen(
                    [self.command] + self.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creation_flags
                )
                self.is_running = True
                
                # Start reader thread
                self._thread = threading.Thread(target=self._read_messages, daemon=True)
                self._thread.start()
                
                # Initialize with protocol handshake
                return self._initialize()
            except Exception:
                self.is_running = False
                if self.process:
                    self.process.terminate()
                return False

    def stop(self) -> bool:
        """Stop the MCP server process."""
        with self._lock:
            if not self.is_running:
                return True
                
            try:
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                self.is_running = False
                self.process = None
                return True
            except Exception:
                return False

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from this server."""
        if not self.is_running:
            return []
        
        try:
            result = self._jsonrpc_call("tools/list", {})
            if result and "tools" in result:
                self.tools = result["tools"]
            return self.tools
        except Exception:
            return []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on this MCP server."""
        if not self.is_running:
            return f"Error: MCP server '{self.name}' is not running"
        
        try:
            result = self._jsonrpc_call("tools/call", {
                "name": name,
                "arguments": arguments
            })
            
            if not result or "content" not in result:
                return "No response from tool"
            
            # Format the response
            contents = result["content"]
            if isinstance(contents, list):
                parts = []
                for item in contents:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            parts.append(f"[Image: {item.get('mimeType', 'unknown')}]")
                        elif item.get("type") == "resource":
                            parts.append(item.get("resource", {}).get("text", ""))
                        else:
                            parts.append(json.dumps(item))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            else:
                return json.dumps(contents)
                
        except Exception as e:
            return f"Error calling tool '{name}': {str(e)}"

    def _jsonrpc_call(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a JSON-RPC call and wait for response."""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Send request
        with self._lock:
            if self.process and self.process.stdin:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
        
        # Wait for response
        response = self._pending.get(request_id, None)
        if response is not None:
            del self._pending[request_id]
            return response
        
        return None

    def _initialize(self) -> bool:
        """Initialize connection with MCP server."""
        try:
            result = self._jsonrpc_call("initialize", {
                "protocolVersion": 1,
                "capabilities": {},
                "clientInfo": {
                    "name": "MCPABZ Agent Codex",
                    "version": "1.0.0"
                }
            })
            
            if result:
                return True
            return False
        except Exception:
            return False

    def _read_messages(self):
        """Read messages from server stdout."""
        try:
            while self.is_running and self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                try:
                    message = json.loads(line)
                    if "id" in message:
                        # Store response for pending request
                        with self._lock:
                            if message["id"] in self._pending:
                                self._pending[message["id"]] = message.get("result")
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        finally:
            self.is_running = False


class MCPClient:
    """Client for managing multiple MCP servers."""
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.config_file = Path(__file__).parent / "mcp_config.json"

    def load_config(self) -> bool:
        """Load MCP server configuration from file."""
        try:
            if self.config_file.exists():
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                for server_config in config.get("servers", []):
                    server = MCPServer(
                        name=server_config["name"],
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        description=server_config.get("description", "")
                    )
                    self.servers[server.name] = server
                return True
        except Exception:
            pass
        return False

    def save_config(self) -> bool:
        """Save MCP server configuration to file."""
        try:
            config = {
                "servers": [
                    {
                        "name": server.name,
                        "command": server.command,
                        "args": server.args,
                        "description": server.description
                    }
                    for server in self.servers.values()
                ]
            }
            self.config_file.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
        except Exception:
            return False

    def add_server(self, name: str, command: str, args: List[str] = None, description: str = "") -> MCPServer:
        """Add an MCP server."""
        server = MCPServer(name, command, args or [], description)
        self.servers[name] = server
        self.save_config()
        return server

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server."""
        if name in self.servers:
            self.servers[name].stop()
            del self.servers[name]
            self.save_config()
            return True
        return False

    def start_server(self, name: str) -> bool:
        """Start an MCP server."""
        if name in self.servers:
            return self.servers[name].start()
        return False

    def stop_server(self, name: str) -> bool:
        """Stop an MCP server."""
        if name in self.servers:
            return self.servers[name].stop()
        return False

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all running servers."""
        all_tools = []
        for server in self.servers.values():
            if server.is_running:
                tools = server.get_tools()
                # Format tools to match OpenAI function calling format
                for tool in tools:
                    formatted_tool = {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{server.name}_{tool['name']}",
                            "description": f"[MCP:{server.name}] {tool.get('description', '')}",
                            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})
                        }
                    }
                    all_tools.append(formatted_tool)
        return all_tools

    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool by its formatted name."""
        # Parse the mcp_servername_toolname format
        parts = tool_name.split("_", 2)
        if len(parts) < 3:
            return f"Error: Invalid MCP tool name format: {tool_name}"
        
        server_name = parts[1]
        original_name = "_".join(parts[2:])
        
        if server_name not in self.servers:
            return f"Error: MCP server '{server_name}' not found"
        
        server = self.servers[server_name]
        return server.call_tool(original_name, arguments)

    def cleanup(self):
        """Stop all MCP servers."""
        for server in self.servers.values():
            server.stop()
