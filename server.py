# server.py
import httpx

from fastmcp import FastMCP
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
    mcp.run()