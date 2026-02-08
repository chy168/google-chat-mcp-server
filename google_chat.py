import os
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
    'https://www.googleapis.com/auth/userinfo.profile',
]

# Cache for user display names: {user_id: display_name}
_user_display_name_cache: Dict[str, str] = {}
DEFAULT_CALLBACK_URL = "http://localhost:8000/auth/callback"
DEFAULT_TOKEN_PATH = 'token.json'

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
        spaces = service.spaces().list(pageSize=30).execute()
        return spaces.get('spaces', [])
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
    
