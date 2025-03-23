# server.py
import httpx
import sys
import argparse
from typing import List, Dict

from fastmcp import FastMCP
from google_chat import list_chat_spaces, run_auth_server, DEFAULT_CALLBACK_URL, set_token_path

# Create an MCP server
mcp = FastMCP("Demo")

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

name = "GG"

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.weather.com/{city}"
        )
        return response.text

@mcp.tool()
async def get_ip_my_address(city: str) -> str:
    """Get IP address from outian.net"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://outian.net/"
        )
        return response.text

@mcp.tool()
async def get_chat_spaces() -> List[Dict]:
    """List all Google Chat spaces the bot has access to.
    
    This tool requires OAuth authentication. On first run, it will open a browser window
    for you to log in with your Google account. Make sure you have credentials.json
    downloaded from Google Cloud Console in the current directory.
    """
    return await list_chat_spaces()

# @app.tool()
# def get_ip() -> MCPResponse[Dict[str, str]]:
#     """Get IP address from outian.net"""
#     try:
#         response = requests.get("https://outian.net/")
#         if response.status_code == 200:
#             return MCPResponse(data={"ip": response.text.strip()})
#         else:
#             return MCPResponse(error="Failed to get IP from outian.net", status_code=500)
#     except Exception as e:
#         return MCPResponse(error=str(e), status_code=500)

# @app.tool()
# def list_files(path: str) -> MCPResponse[Dict[str, List[str]]]:
#     """List files in the specified directory"""
#     try:
#         if not os.path.exists(path):
#             return MCPResponse(error=f"Path not found: {path}", status_code=404)
        
#         files = os.listdir(path)
#         return MCPResponse(data={"files": files})
#     except Exception as e:
#         return MCPResponse(error=str(e), status_code=500)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MCP Server with Google Chat Authentication')
    parser.add_argument('-local-auth', action='store_true', help='Run the local authentication server')
    parser.add_argument('--host', default='localhost', help='Host to bind the server to (default: localhost)')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    parser.add_argument('--token-path', default='token.json', help='Path to store OAuth token (default: token.json)')
    
    args = parser.parse_args()
    
    # Set the token path for OAuth storage
    set_token_path(args.token_path)
    
    if args.local_auth:
        print(f"\nStarting local authentication server at http://{args.host}:{args.port}")
        print("Available endpoints:")
        print("  - /auth   : Start OAuth authentication flow")
        print("  - /status : Check authentication status")
        print("  - /auth/callback : OAuth callback endpoint")
        print(f"\nDefault callback URL: {DEFAULT_CALLBACK_URL}")
        print(f"Token will be stored at: {args.token_path}")
        print("\nPress CTRL+C to stop the server")
        print("-" * 50)
        run_auth_server(port=args.port, host=args.host)
    else:
        mcp.run()