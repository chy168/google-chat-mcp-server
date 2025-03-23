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
    'https://www.googleapis.com/auth/chat.messages'
]
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

# MCP functions
async def list_chat_spaces() -> List[Dict]:
    """Lists all Google Chat spaces the bot has access to."""
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("No valid credentials found. Please authenticate first.")
            
        service = build('chat', 'v1', credentials=creds)
        spaces = service.spaces().list().execute()
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
        
        # Make API request
        request = service.spaces().messages().list(parent=space_name)
        if filter_str:
            request = service.spaces().messages().list(parent=space_name, filter=filter_str)
            
        response = request.execute()
        return response.get('messages', [])
        
    except Exception as e:
        raise Exception(f"Failed to list messages in space: {str(e)}")
    
