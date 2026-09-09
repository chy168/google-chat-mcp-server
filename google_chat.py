import os
# Google may return additional scopes previously granted (include_granted_scopes),
# so relax the strict scope-match check oauthlib otherwise enforces.
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

import json
import datetime
from typing import List, Dict, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pathlib import Path

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/chat.spaces.readonly',
    'https://www.googleapis.com/auth/chat.messages',
    'https://www.googleapis.com/auth/chat.messages.reactions',
    'https://www.googleapis.com/auth/chat.memberships.readonly',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/directory.readonly',
]

# Cache for user display names: {user_id: display_name}
_user_display_name_cache: Dict[str, str] = {}
DEFAULT_CALLBACK_URL = "http://localhost:8000/auth/callback"
DEFAULT_TOKEN_PATH = 'token.json'

# Holds the in-progress OAuth flow between a start_authentication() and
# complete_authentication() call, since they happen as two separate tool calls.
_pending_auth_flow: Optional[InstalledAppFlow] = None

# Store credentials info
token_info = {
    'credentials': None,
    'last_refresh': None,
    'token_path': DEFAULT_TOKEN_PATH
}

def set_token_path(path: str) -> None:
    """Set the global token path for OAuth storage.
    
    Args:
        path: Path where the token should be stored
    """
    token_info['token_path'] = path

# Global flag for message filtering
SAVE_TOKEN_MODE = True

def set_save_token_mode(enabled: bool) -> None:
    """Set whether to filter message fields to save tokens.
    
    Args:
        enabled: True to enable filtering, False to disable
    """
    global SAVE_TOKEN_MODE
    SAVE_TOKEN_MODE = enabled

def save_credentials(creds: Credentials, token_path: Optional[str] = None) -> None:
    """Save credentials to file and update in-memory cache.
    
    Args:
        creds: The credentials to save
        token_path: Path to save the token file
    """
    # Use configured token path if none provided
    if token_path is None:
        token_path = token_info['token_path']
    
    # Save to file
    token_path = Path(token_path)
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    
    # Update in-memory cache
    token_info['credentials'] = creds
    token_info['last_refresh'] = datetime.datetime.utcnow()

def get_credentials(token_path: Optional[str] = None) -> Optional[Credentials]:
    """Gets valid user credentials from storage or memory.
    
    Args:
        token_path: Optional path to token file. If None, uses the configured path.
    
    Returns:
        Credentials object or None if no valid credentials exist
    """
    if token_path is None:
        token_path = token_info['token_path']
    
    creds = token_info['credentials']
    
    # If no credentials in memory, try to load from file
    if not creds:
        token_path = Path(token_path)
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            token_info['credentials'] = creds
    
    # If we have credentials that need refresh
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds, token_path)
        except Exception:
            return None
    
    return creds if (creds and creds.valid) else None

async def refresh_token(token_path: Optional[str] = None) -> Tuple[bool, str]:
    """Attempt to refresh the current token.
    
    Args:
        token_path: Path to the token file. If None, uses the configured path.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if token_path is None:
        token_path = token_info['token_path']
        
    try:
        creds = token_info['credentials']
        if not creds:
            token_path = Path(token_path)
            if not token_path.exists():
                return False, "No token file found"
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        if not creds.refresh_token:
            return False, "No refresh token available"
        
        creds.refresh(Request())
        save_credentials(creds, token_path)
        return True, "Token refreshed successfully"
    except Exception as e:
        return False, f"Failed to refresh token: {str(e)}"

def get_user_display_name(sender: Dict, creds: Credentials) -> str:
    """Get user display name with caching.

    For HUMAN users: Uses People API to fetch display name.
    For BOT users: Uses displayName from Chat API if available, otherwise returns bot identifier.

    Args:
        sender: The sender object from Chat API (contains 'name', 'type', optionally 'displayName')
        creds: Valid credentials for API calls

    Returns:
        User's display name, or a fallback identifier if lookup fails
    """
    user_id = sender.get('name', '')
    sender_type = sender.get('type', 'HUMAN')

    # Check if already cached
    if user_id in _user_display_name_cache:
        return _user_display_name_cache[user_id]

    # If Chat API already provided displayName, use it
    if sender.get('displayName'):
        _user_display_name_cache[user_id] = sender['displayName']
        return sender['displayName']

    # For BOT type, we can't use People API
    if sender_type == 'BOT':
        # Extract short ID for readability
        short_id = user_id.replace('users/', '') if user_id else 'unknown'
        display_name = f"Bot ({short_id[:8]}...)"
        _user_display_name_cache[user_id] = display_name
        return display_name

    # For HUMAN type, try People API
    try:
        person_id = user_id.replace('users/', 'people/')

        service = build('people', 'v1', credentials=creds)
        person = service.people().get(
            resourceName=person_id,
            personFields='names'
        ).execute()

        names = person.get('names', [])
        if names:
            display_name = names[0].get('displayName', user_id)
        else:
            display_name = user_id

        _user_display_name_cache[user_id] = display_name
        return display_name
    except Exception as e:
        # If lookup fails, cache and return the original user_id
        _user_display_name_cache[user_id] = user_id
        return user_id


# MCP functions
async def list_chat_spaces() -> List[Dict]:
    """Lists all Google Chat spaces the bot has access to."""
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)

        spaces = []
        page_token = None

        while True:
            list_args = {'pageSize': 1000}
            if page_token:
                list_args['pageToken'] = page_token

            response = service.spaces().list(**list_args).execute()

            current_page_spaces = response.get('spaces', [])
            if current_page_spaces:
                spaces.extend(current_page_spaces)

            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return spaces
    except Exception as e:
        raise Exception(f"Failed to list chat spaces: {str(e)}")

async def list_space_messages(space_name: str, 
                            start_date: Optional[datetime.datetime] = None,
                            end_date: Optional[datetime.datetime] = None) -> List[Dict]:
    """Lists messages from a specific Google Chat space with optional time filtering.
    
    Args:
        space_name: The name/identifier of the space to fetch messages from
        start_date: Optional start datetime for filtering messages. If provided without end_date,
                   will query messages for the entire day of start_date
        end_date: Optional end datetime for filtering messages. Only used if start_date is also provided
    
    Returns:
        List of message objects from the space matching the time criteria
        
    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")
            
        service = build('chat', 'v1', credentials=creds)
        
        # Prepare filter string based on provided dates
        filter_str = None
        if start_date:
            if end_date:
                # Format for date range query
                filter_str = f"createTime > \"{start_date.isoformat()}\" AND createTime < \"{end_date.isoformat()}\""
            else:
                # For single day query, set range from start of day to end of day
                day_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + datetime.timedelta(days=1)
                filter_str = f"createTime > \"{day_start.isoformat()}\" AND createTime < \"{day_end.isoformat()}\""
        
        # Make API request with pagination
        messages = []
        page_token = None
        
        while True:
            list_args = {
                'parent': space_name,
                'pageSize': 100
            }
            if filter_str:
                list_args['filter'] = filter_str
            if page_token:
                list_args['pageToken'] = page_token
                
            response = service.spaces().messages().list(**list_args).execute()
            
            # Extend messages list with current page results
            current_page_messages = response.get('messages', [])
            if current_page_messages:
                messages.extend(current_page_messages)
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        if not SAVE_TOKEN_MODE:
            return messages

        filtered_messages = []
        for msg in messages:
            sender = msg.get('sender', {})
            display_name = get_user_display_name(sender, creds) if sender else 'Unknown'

            filtered_msg = {
                'sender': display_name,
                'createTime': msg.get('createTime'),
                'text': msg.get('text'),
                'thread': msg.get('thread')
            }
            filtered_messages.append(filtered_msg)

        return filtered_messages
        
    except Exception as e:
        raise Exception(f"Failed to list messages in space: {str(e)}")

async def send_message(space_name: str, text: str, thread_id: Optional[str] = None,
                        message_id: Optional[str] = None) -> Dict:
    """Sends a text message to a specific Google Chat space, optionally as a reply in a thread.

    Args:
        space_name: The name/identifier of the space to send the message to (e.g. 'spaces/AAAA1234')
        text: The message text to send
        thread_id: Optional thread identifier to reply within (e.g. 'AAAA1234' or the full
                   'spaces/.../threads/AAAA1234' name). If omitted, a new thread is started.
        message_id: Optional custom message ID to assign (must start with 'client-', up to 63
                    chars, lowercase letters/numbers/hyphens only, unique within the space).
                    Lets you reference this message later without the system-assigned name.

    Returns:
        The created message object

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)

        body = {'text': text}
        create_args = {'parent': space_name, 'body': body}

        if thread_id:
            thread_name = thread_id if thread_id.startswith('spaces/') else f"{space_name}/threads/{thread_id}"
            body['thread'] = {'name': thread_name}
            create_args['messageReplyOption'] = 'REPLY_MESSAGE_OR_FAIL'

        if message_id:
            create_args['messageId'] = message_id

        return service.spaces().messages().create(**create_args).execute()
    except Exception as e:
        raise Exception(f"Failed to send message to space: {str(e)}")


def _resolve_message_name(space_name: str, message_id: str) -> str:
    """Resolves a message resource name from either a full name or a client-assigned ID.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either a full message name ('spaces/.../messages/...') or a
                    client-assigned ID ('client-my-id')

    Returns:
        The full message resource name
    """
    if message_id.startswith('spaces/'):
        return message_id
    return f"{space_name}/messages/{message_id}"


async def get_message(space_name: str, message_id: str) -> Dict:
    """Gets a single message's full details.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID (from its resource name,
                    e.g. 'AAAA.BBBB') or a client-assigned ID (e.g. 'client-my-id')

    Returns:
        The message object

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)
        message_name = _resolve_message_name(space_name, message_id)

        return service.spaces().messages().get(name=message_name).execute()
    except Exception as e:
        raise Exception(f"Failed to get message: {str(e)}")


async def update_message(space_name: str, message_id: str, text: str) -> Dict:
    """Updates the text of an existing message that this app sent.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID
        text: The new message text

    Returns:
        The updated message object

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)
        message_name = _resolve_message_name(space_name, message_id)

        return service.spaces().messages().patch(
            name=message_name,
            updateMask='text',
            body={'text': text}
        ).execute()
    except Exception as e:
        raise Exception(f"Failed to update message: {str(e)}")


async def delete_message(space_name: str, message_id: str) -> Dict:
    """Deletes a message that this app sent.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID

    Returns:
        An empty dict on success

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)
        message_name = _resolve_message_name(space_name, message_id)

        service.spaces().messages().delete(name=message_name).execute()
        return {}
    except Exception as e:
        raise Exception(f"Failed to delete message: {str(e)}")


async def search_messages(space_name: str, query: str,
                           start_date: Optional[datetime.datetime] = None,
                           end_date: Optional[datetime.datetime] = None) -> List[Dict]:
    """Searches messages in a space for a keyword/substring match.

    The Chat API's message list filter only supports filtering by createTime and thread,
    not message content, so this fetches messages (optionally time-bounded) and filters
    them client-side by a case-insensitive substring match on the message text.

    Args:
        space_name: The name/identifier of the space to search in
        query: Case-insensitive substring to search for in message text
        start_date: Optional start datetime to bound the search
        end_date: Optional end datetime to bound the search

    Returns:
        List of message objects whose text contains the query

    Raises:
        Exception: If authentication fails or API request fails
    """
    messages = await list_space_messages(space_name, start_date, end_date)
    query_lower = query.lower()
    return [msg for msg in messages if query_lower in (msg.get('text') or '').lower()]


async def get_space_members(space_name: str) -> List[Dict]:
    """Lists the members of a specific Google Chat space.

    Args:
        space_name: The name/identifier of the space (e.g. 'spaces/AAAA1234')

    Returns:
        List of membership objects for the space

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)

        members = []
        page_token = None

        while True:
            list_args = {'parent': space_name, 'pageSize': 1000}
            if page_token:
                list_args['pageToken'] = page_token

            response = service.spaces().members().list(**list_args).execute()

            current_page_members = response.get('memberships', [])
            if current_page_members:
                members.extend(current_page_members)

            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return members
    except Exception as e:
        raise Exception(f"Failed to list space members: {str(e)}")


async def create_reaction(space_name: str, message_id: str, emoji: str) -> Dict:
    """Adds an emoji reaction to a message.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID
        emoji: The unicode emoji character to react with (e.g. '👍')

    Returns:
        The created reaction object

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)
        message_name = _resolve_message_name(space_name, message_id)

        # The reactions endpoint rejects client-assigned message IDs in the parent
        # path (unlike get/patch/delete), so resolve to the system-assigned name first.
        if '/messages/client-' in message_name:
            message = service.spaces().messages().get(name=message_name).execute()
            message_name = message['name']

        return service.spaces().messages().reactions().create(
            parent=message_name,
            body={'emoji': {'unicode': emoji}}
        ).execute()
    except Exception as e:
        raise Exception(f"Failed to create reaction: {str(e)}")


async def list_reactions(space_name: str, message_id: str) -> List[Dict]:
    """Lists the emoji reactions on a message.

    Args:
        space_name: The space the message belongs to (e.g. 'spaces/AAAA1234')
        message_id: Either the message's system-assigned ID or a client-assigned ID

    Returns:
        List of reaction objects on the message

    Raises:
        Exception: If authentication fails or API request fails
    """
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")

        service = build('chat', 'v1', credentials=creds)
        message_name = _resolve_message_name(space_name, message_id)

        # The reactions endpoint rejects client-assigned message IDs in the parent
        # path (unlike get/patch/delete), so resolve to the system-assigned name first.
        if '/messages/client-' in message_name:
            message = service.spaces().messages().get(name=message_name).execute()
            message_name = message['name']

        reactions = []
        page_token = None

        while True:
            list_args = {'parent': message_name, 'pageSize': 100}
            if page_token:
                list_args['pageToken'] = page_token

            response = service.spaces().messages().reactions().list(**list_args).execute()

            current_page_reactions = response.get('reactions', [])
            if current_page_reactions:
                reactions.extend(current_page_reactions)

            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return reactions
    except Exception as e:
        raise Exception(f"Failed to list reactions: {str(e)}")


def start_authentication(credentials_path: str = 'credentials.json') -> str:
    """Starts an OAuth authentication flow and returns the authorization URL.

    The user should open the URL, complete authorization, then pass the resulting
    callback URL to complete_authentication() to finish the flow.

    Args:
        credentials_path: Path to the OAuth client credentials.json file

    Returns:
        The authorization URL for the user to open in a browser

    Raises:
        Exception: If credentials.json is missing or the flow can't be created
    """
    global _pending_auth_flow

    creds_file = Path(credentials_path)
    if not creds_file.exists():
        raise Exception(
            f"{credentials_path} not found. Download it from Google Cloud Console "
            "and save it in the current directory."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_file),
        SCOPES,
        redirect_uri=DEFAULT_CALLBACK_URL
    )

    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )

    _pending_auth_flow = flow
    return auth_url


def complete_authentication(callback_url: str, token_path: Optional[str] = None) -> Dict:
    """Completes an OAuth flow started by start_authentication() using the callback URL.

    Args:
        callback_url: The full callback URL from the browser address bar after authorizing
                      (e.g. 'http://localhost:8000/auth/callback?code=...&scope=...'), or
                      just the bare authorization code
        token_path: Optional path to save the token to. If None, uses the configured path.

    Returns:
        A dict with authentication status details

    Raises:
        Exception: If no authentication flow is in progress, the callback has no code,
                   or the code exchange fails
    """
    global _pending_auth_flow

    if _pending_auth_flow is None:
        raise Exception(
            "No authentication flow in progress. Call start_authentication() first."
        )

    from urllib.parse import urlparse, parse_qs

    if callback_url.startswith('http'):
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)

        if 'error' in params:
            raise Exception(f"Authorization failed: {params['error'][0]}")

        if 'code' not in params:
            raise Exception("No authorization code found in the callback URL.")

        code = params['code'][0]
    else:
        code = callback_url

    try:
        flow = _pending_auth_flow
        flow.fetch_token(code=code)
        creds = flow.credentials

        save_credentials(creds, token_path)

        return {
            'authenticated': True,
            'has_refresh_token': bool(creds.refresh_token),
            'expiry': creds.expiry.isoformat() if creds.expiry else None,
        }
    finally:
        _pending_auth_flow = None

