# server.py
import httpx
import sys
import argparse
from typing import List, Dict

from fastmcp import FastMCP
from google_chat import list_chat_spaces, DEFAULT_CALLBACK_URL, set_token_path, set_save_token_mode
from server_auth import run_auth_server
from auth_cli import run_cli_auth

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

@mcp.tool()
async def get_space_messages(space_name: str, 
                           start_date: str,
                           end_date: str = None) -> List[Dict]:
    """List messages from a specific Google Chat space with optional time filtering.
    
    This tool requires OAuth authentication. The space_name should be in the format
    'spaces/your_space_id'. Dates should be in YYYY-MM-DD format (e.g., '2024-03-22').
    
    When only start_date is provided, it will query messages for that entire day.
    When both dates are provided, it will query messages from start_date 00:00:00Z
    to end_date 23:59:59Z.
    
    Args:
        space_name: The name/identifier of the space to fetch messages from
        start_date: Required start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    
    Returns:
        List of message objects from the space matching the time criteria
        
    Raises:
        ValueError: If the date format is invalid or dates are in wrong order
    """
    from google_chat import list_space_messages
    from datetime import datetime, timezone

    try:
        # Parse start date and set to beginning of day (00:00:00Z)
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d').replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        
        # Parse end date if provided and set to end of day (23:59:59Z)
        end_datetime = None
        if end_date:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )
            
            # Validate date range
            if start_datetime > end_datetime:
                raise ValueError("start_date must be before end_date")
    except ValueError as e:
        if "strptime" in str(e):
            raise ValueError("Dates must be in YYYY-MM-DD format (e.g., '2024-03-22')")
        raise e
    
    return await list_space_messages(space_name, start_datetime, end_datetime)

@mcp.tool()
async def send_message(space_name: str, text: str, thread_id: str = None,
                        message_id: str = None) -> Dict:
    """Send a text message to a specific Google Chat space, optionally as a reply in a thread.

    This tool requires OAuth authentication with the chat.messages scope. The space_name
    should be in the format 'spaces/your_space_id'. This will post a visible message to
    the space, so double-check the space_name, thread_id, and text before calling.

    To reply within an existing thread, pass thread_id. A Google Chat message/thread URL
    looks like 'https://chat.google.com/room/{spaceId}/{threadId}/{messageId}' - space_name
    is 'spaces/{spaceId}' and thread_id is the {threadId} segment. If thread_id is omitted,
    a new thread is started.

    Args:
        space_name: The name/identifier of the space to send the message to
        text: The message text to send
        thread_id: Optional thread identifier (the {threadId} segment from a chat.google.com
                   message link) to reply within an existing thread instead of starting a new one
        message_id: Optional custom message ID to assign, so you can reference this message
                   later without the system-assigned name. Must start with 'client-', up to
                   63 chars, lowercase letters/numbers/hyphens only, unique within the space.

    Returns:
        The created message object
    """
    from google_chat import send_message as _send_message
    return await _send_message(space_name, text, thread_id, message_id)

@mcp.tool()
async def get_message(space_name: str, message_id: str) -> Dict:
    """Get a single message's full details from a Google Chat space.

    Args:
        space_name: The name/identifier of the space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID (the part after 'messages/' in its
                   resource name) or a client-assigned ID (e.g. 'client-my-id') set via send_message

    Returns:
        The message object
    """
    from google_chat import get_message as _get_message
    return await _get_message(space_name, message_id)

@mcp.tool()
async def update_message(space_name: str, message_id: str, text: str) -> Dict:
    """Update the text of an existing message that this app sent.

    This will visibly edit the message for everyone in the space, so double-check
    space_name, message_id, and the new text before calling.

    Args:
        space_name: The name/identifier of the space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID
        text: The new message text

    Returns:
        The updated message object
    """
    from google_chat import update_message as _update_message
    return await _update_message(space_name, message_id, text)

@mcp.tool()
async def delete_message(space_name: str, message_id: str) -> Dict:
    """Delete a message that this app sent.

    This permanently removes the message from the space for everyone, so double-check
    space_name and message_id before calling.

    Args:
        space_name: The name/identifier of the space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID

    Returns:
        An empty dict on success
    """
    from google_chat import delete_message as _delete_message
    return await _delete_message(space_name, message_id)

@mcp.tool()
async def search_messages(space_name: str, query: str,
                           start_date: str = None, end_date: str = None) -> List[Dict]:
    """Search messages in a Google Chat space for a keyword/substring match.

    The Chat API doesn't support full-text search server-side, so this fetches messages
    (optionally time-bounded, same date rules as get_space_messages) and filters them
    for a case-insensitive substring match on the message text.

    Args:
        space_name: The name/identifier of the space to search in
        query: Case-insensitive substring to search for in message text
        start_date: Optional start date in YYYY-MM-DD format to bound the search
        end_date: Optional end date in YYYY-MM-DD format to bound the search

    Returns:
        List of message objects whose text contains the query
    """
    from google_chat import search_messages as _search_messages
    from datetime import datetime, timezone

    start_datetime = None
    end_datetime = None
    if start_date:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d').replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
    if end_date:
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
        )

    return await _search_messages(space_name, query, start_datetime, end_datetime)

@mcp.tool()
async def get_space_members(space_name: str) -> List[Dict]:
    """List the members of a specific Google Chat space.

    Args:
        space_name: The name/identifier of the space (e.g. 'spaces/AAAA1234')

    Returns:
        List of membership objects for the space
    """
    from google_chat import get_space_members as _get_space_members
    return await _get_space_members(space_name)

@mcp.tool()
async def create_reaction(space_name: str, message_id: str, emoji: str) -> Dict:
    """Add an emoji reaction to a message in a Google Chat space.

    Args:
        space_name: The name/identifier of the space the message belongs to
        message_id: Either the message's system-assigned ID or a client-assigned ID
        emoji: The unicode emoji character to react with (e.g. '👍')

    Returns:
        The created reaction object
    """
    from google_chat import create_reaction as _create_reaction
    return await _create_reaction(space_name, message_id, emoji)

@mcp.tool()
async def list_reactions(space_name: str, message_id: str) -> List[Dict]:
    """List the emoji reactions on a message in a Google Chat space.

    Args:
        space_name: The name/identifier of the space the message belongs to
        message_id: Either the message's system-assigned ID or a client-assigned ID

    Returns:
        List of reaction objects on the message
    """
    from google_chat import list_reactions as _list_reactions
    return await _list_reactions(space_name, message_id)

@mcp.tool()
def authenticate() -> str:
    """Start (or restart) Google Chat OAuth authentication.

    Call this if another tool fails with a credentials/authentication error. It returns
    an authorization URL - share it with the user and ask them to open it in a browser and
    complete authorization. Once they do, call complete_authentication with the resulting
    callback URL to finish.

    Returns:
        The authorization URL for the user to open in a browser
    """
    from google_chat import start_authentication
    return start_authentication()

@mcp.tool()
def complete_authentication(callback_url: str) -> Dict:
    """Complete an in-progress OAuth flow for Google Chat.

    Call authenticate first to start the flow and get the authorization URL. After the
    user authorizes in their browser, it redirects to a
    'http://localhost:8000/auth/callback?code=...&scope=...' URL - that page will likely
    fail to load, but the URL in the browser's address bar is still valid. Pass that full
    URL here as callback_url (a bare code also works).

    Args:
        callback_url: The full callback URL from the browser address bar after authorizing

    Returns:
        A dict with authentication status details
    """
    from google_chat import complete_authentication as _complete_authentication
    return _complete_authentication(callback_url)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MCP Server with Google Chat Authentication')
    parser.add_argument('--auth', choices=['web', 'cli'],
                        help='Run OAuth authentication (web: browser-based, cli: headless/terminal)')
    parser.add_argument('--host', default='localhost', help='Host to bind the auth server to (default: localhost)')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the auth server on (default: 8000)')
    parser.add_argument('--token-path', default='token.json', help='Path to store OAuth token (default: token.json)')
    parser.add_argument('--disable-token-saving', action='store_false', help='Disable token saving mode (enabled by default)')

    args = parser.parse_args()

    # Set the token path for OAuth storage
    set_token_path(args.token_path)

    # Set message filtering
    set_save_token_mode(args.disable_token_saving)

    if args.auth == 'web':
        print(f"\nStarting OAuth authentication server at http://{args.host}:{args.port}")
        print("Available endpoints:")
        print("  - /auth   : Start OAuth authentication flow")
        print("  - /status : Check authentication status")
        print("  - /auth/callback : OAuth callback endpoint")
        print(f"\nDefault callback URL: {DEFAULT_CALLBACK_URL}")
        print(f"Token will be stored at: {args.token_path}")
        print("\nPress CTRL+C to stop the server")
        print("-" * 50)
        run_auth_server(port=args.port, host=args.host)
    elif args.auth == 'cli':
        run_cli_auth()
    else:
        mcp.run()