"""
Whoop API client for accessing Whoop data using both official and unofficial API endpoints.

This client supports both the official Whoop API for reading data and the unofficial API endpoints
needed for creating workouts and linking them to strength training activities.

Official API documentation: https://developer.whoop.com/api/
"""

import os
import json
import logging
import requests
import random
import time
from datetime import datetime, timedelta
import pytz

from rate_limiter import RateLimiter, rate_limited

logger = logging.getLogger(__name__)

class WhoopClient:
    """Client for interacting with the official and unofficial Whoop APIs."""
    
    # API endpoints - Using the exact endpoints observed in the Charles transcript
    OFFICIAL_BASE_URL = "https://api.prod.whoop.com/developer"
    OFFICIAL_AUTH_URL = "https://api.prod.whoop.com/oauth/token"
    
    # Base URL - From the Charles transcript, all requests use this host
    UNOFFICIAL_BASE_URL = "https://api.prod.whoop.com"
    
    # Workout-related endpoints (from Charles transcript)
    WORKOUT_CREATE_ENDPOINT = "/activities-service/v0/workouts"  # POST - for creating workouts
    WORKOUT_LINK_ENDPOINT = "/weightlifting-service/v1/link-workout"  # GET - for linking workouts
    WEIGHTLIFTING_WORKOUT_LINK_ENDPOINT = "/weightlifting-service/v2/weightlifting-workout/link-cardio-workout"  # POST
    WORKOUT_LIBRARY_ENDPOINT = "/weightlifting-service/v2/workout-library/"  # GET - for workout templates
    WORKOUT_TEMPLATE_ENDPOINT = "/weightlifting-service/v3/workout-template"  # POST - for creating workout templates
    
    # Activity-related endpoints (from Charles transcript)
    CYCLES_ENDPOINT = "/activities-service/v1/cycles/aggregate/range"  # GET - for cycle data
    SPORTS_HISTORY_ENDPOINT = "/activities-service/v1/sports/history"  # GET - for sports history
    ACTIVITY_TYPES_ENDPOINT = "/activities-service/v2/activity-types"  # GET - for activity types
    USER_CREATED_ACTIVITY_ENDPOINT = "/core-details-bff/v2/activity-type/user-created"  # GET
    USER_STATE_ENDPOINT = "/activities-service/v1/user-state"  # GET - for user state
    
    # The most direct activity and workout endpoints for our use case
    WORKOUT_ENDPOINT = WORKOUT_CREATE_ENDPOINT
    ACTIVITY_SEARCH_ENDPOINT = SPORTS_HISTORY_ENDPOINT  # Use sports history to find activities
    
    def __init__(self, credentials):
        """
        Initialize the Whoop API client.
        
        Args:
            credentials (dict): Whoop API credentials
                - client_id: Your OAuth client ID from Whoop developer portal
                - client_secret: Your OAuth client secret from Whoop developer portal
                - refresh_token: Optional refresh token if you have one
                - access_token: Optional access token if you have one
                
                Alternatively, for backwards compatibility:
                - email: Whoop account email (legacy)
                - password: Whoop account password (legacy)
                - api_key: API key (legacy)
        """
        self.credentials = credentials
        self.session = requests.Session()
        self.access_token = credentials.get('access_token')
        self.refresh_token = credentials.get('refresh_token')
        self.token_expires_at = None
        self.authenticated = False if not self.access_token else True
        
        # Initialize rate limiter with conservative settings
        # Use more conservative settings than Peloton because Whoop API is less documented
        requests_per_minute = int(credentials.get('requests_per_minute', 10))  # Very conservative by default
        self.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            max_retries=3,
            base_delay=3.0,
            max_delay=180.0,  # Maximum 3 minute delay between retries
            jitter=0.3
        )
        
        # If access token exists, set it in the session headers
        if self.access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
    
    def authenticate(self):
        """
        Authenticate with the Whoop API using OAuth 2.0 flow.
        
        Returns:
            bool: True if authentication was successful, False otherwise.
        """
        # If we already have a valid access token, no need to authenticate again
        if self.authenticated and self.access_token:
            logger.info("Already authenticated with Whoop API")
            return True
            
        # Check if we have a refresh token to use
        if self.refresh_token:
            logger.info("Attempting to refresh Whoop OAuth token")
            return self._refresh_access_token()
            
        # Legacy authentication fallback
        if self._try_legacy_auth():
            return True
            
        # No valid authentication method available
        logger.error("No valid authentication method available for Whoop API")
        logger.info("To use the official Whoop API, you need to register an application at https://developer.whoop.com")
        logger.info("After registering, add your client_id and client_secret to config.ini")
        return False
    
    def _try_legacy_auth(self):
        """
        Try legacy authentication methods (email/password or API key).
        This is for backward compatibility but may not work with the official API.
        
        Returns:
            bool: True if authentication was successful
        """
        # Try API key first if available
        if 'api_key' in self.credentials and self.credentials['api_key'] and self.credentials['api_key'] != 'your_whoop_api_key':
            logger.info("Attempting legacy API key authentication (not recommended)")
            self.access_token = self.credentials['api_key']
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            # Test if the token works by getting profile info
            try:
                profile = self.get_profile()
                if profile:
                    self.authenticated = True
                    logger.info("Successfully authenticated with legacy API key")
                    return True
            except Exception as e:
                logger.warning(f"Legacy API key authentication failed: {str(e)}")
        
        # Add a delay to avoid rapid authentication attempts
        time.sleep(random.uniform(1.0, 3.0))
        
        # Try email/password if available
        if 'email' in self.credentials and 'password' in self.credentials:
            logger.info("Attempting legacy email/password authentication (not recommended)")
            try:
                # Use the unofficial API login endpoint for email/password auth
                auth_url = "https://api-7.whoop.com/oauth/token"
                auth_payload = {
                    'grant_type': 'password',
                    'client_id': 'whoop-recruiting-prod',  # This is the unofficial client ID that works with the legacy API
                    'username': self.credentials['email'],
                    'password': self.credentials['password']
                }
                
                # Use rate-limited request method
                response = self._make_api_request('post', auth_url, json=auth_payload)
                
                if response.status_code == 200:
                    auth_data = response.json()
                    self.access_token = auth_data.get('access_token')
                    self.refresh_token = auth_data.get('refresh_token')
                    
                    if self.access_token:
                        self.session.headers.update({
                            'Authorization': f'Bearer {self.access_token}'
                        })
                        self.authenticated = True
                        logger.info("Successfully authenticated with legacy email/password")
                        return True
                elif response.status_code == 429:
                    logger.warning("Rate limited during authentication attempt. Waiting...")
                    time.sleep(random.uniform(5.0, 10.0))  # Add extra delay for rate limiting
                    return False
                else:
                    logger.warning(f"Legacy auth failed: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Legacy email/password authentication failed: {str(e)}")
                
        return False
    
    def _refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        
        Returns:
            bool: True if refresh was successful
        """
        try:
            # Ensure we have client credentials and refresh token
            client_id = self.credentials.get('client_id')
            client_secret = self.credentials.get('client_secret')
            
            if not (client_id and client_secret and self.refresh_token):
                logger.error("Missing OAuth credentials for token refresh")
                return False
                
            refresh_payload = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            # Use rate-limited request method
            response = self._make_api_request('post', self.OFFICIAL_AUTH_URL, json=refresh_payload)
            
            if response.status_code == 200:
                auth_data = response.json()
                self.access_token = auth_data.get('access_token')
                self.refresh_token = auth_data.get('refresh_token')  # Update refresh token if provided
                expires_in = auth_data.get('expires_in', 3600)  # Default to 1 hour
                
                # Calculate token expiration time
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update session headers with new token
                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_token}'
                })
                
                self.authenticated = True
                logger.info("Successfully refreshed Whoop API access token")
                return True
            elif response.status_code == 429:
                logger.warning("Rate limited during token refresh. Waiting before retrying...")
                time.sleep(random.uniform(5.0, 10.0))  # Add extra delay for rate limiting
                return False
            else:
                logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing access token: {str(e)}")
            return False
    
    def _make_api_request(self, method, url, **kwargs):
        """
        Make an API request with rate limiting and retry logic.
        
        Args:
            method (str): HTTP method (get, post, etc.)
            url (str): URL to request
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            requests.Response: The response object
            
        Raises:
            Exception: If the request fails after all retries
        """
        # Get the method from the session
        request_method = getattr(self.session, method.lower())
            
        # Make the request with rate limiting via wrapped function
        # Use our rate limiter directly
        return self.rate_limiter.execute_with_retry(lambda: request_method(url, **kwargs))
    
    def _ensure_authenticated(self):
        """Ensure the client is authenticated before making API calls."""
        if not self.authenticated:
            authenticated = self.authenticate()
            if not authenticated:
                raise RuntimeError("Failed to authenticate with Whoop API")
    
    def get_profile(self):
        """
        Get the user's basic profile information.
        Official endpoint: getProfileBasic
        
        Returns:
            dict: User profile information
        """
        self._ensure_authenticated()
        
        endpoint = f"{self.OFFICIAL_BASE_URL}/v1/user/profile/basic"
        
        try:
            # Use rate-limited request method
            response = self._make_api_request('get', endpoint)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limited when retrieving user profile. Waiting...")
                time.sleep(random.uniform(3.0, 5.0))
                return None
            else:
                logger.error(f"Error retrieving user profile: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error retrieving user profile: {str(e)}")
            return None
    
    def find_strength_training_activities(self, days_ago=30):
        """
        Find all strength training activities from the past N days using the
        exact API endpoint patterns observed in the Charles transcript.
        
        Args:
            days_ago: Number of days in the past to check
            
        Returns:
            list: List of strength training activities
        """
        self._ensure_authenticated()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_ago)
        
        logger.info(f"Retrieving activities from {start_date} to {end_date}")
        
        # Format the dates using the format observed in the Charles transcript
        # Example: 2025-04-20T07:00:00.000Z
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Headers observed in the Charles transcript
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-whoop-device-platform': 'API',
            'locale': 'en_US'
        }
        
        # First try the sports history endpoint (GET)
        endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.SPORTS_HISTORY_ENDPOINT}"
        logger.info(f"Fetching strength activities from: {endpoint}")
        
        try:
            # In the Charles transcript, this appears as a GET request
            # with startTime and endTime parameters
            params = {
                'startTime': start_date_str,
                'endTime': end_date_str,
                'limit': 50  # Default limit observed in transcript
            }
            
            response = self._make_api_request('get', endpoint, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                strength_activities = []
                
                # Based on Charles transcript, look for sport_id=1 (Strength Training)
                # First, check the structure of the response
                if isinstance(data, list):
                    # List of activities
                    activities = data
                elif isinstance(data, dict) and 'records' in data:
                    # Page of records
                    activities = data.get('records', [])
                elif isinstance(data, dict) and 'data' in data:
                    # Data container
                    activities = data.get('data', [])
                else:
                    # Unknown format, try to extract anything that looks like an activity
                    activities = data if isinstance(data, dict) and 'id' in data else []
                    if not isinstance(activities, list):
                        activities = [activities]
                
                # Filter for strength training activities
                for activity in activities:
                    if not isinstance(activity, dict):
                        continue
                    
                    # Look for sport_id=1 (Strength Training) or similar indicators
                    sport_id = activity.get('sport_id')
                    if sport_id == 1:  # 1 = Strength Training in Whoop
                        strength_activities.append(activity)
                        continue
                    
                    # Check if it has a sport property with id=1
                    sport = activity.get('sport', {})
                    if isinstance(sport, dict) and sport.get('id') == 1:
                        strength_activities.append(activity)
                        continue
                    
                    # Check for strength training in the name or type
                    activity_type = activity.get('type', '').lower()
                    activity_name = activity.get('name', '').lower()
                    if 'strength' in activity_type or 'weight' in activity_type or \
                       'strength' in activity_name or 'weight' in activity_name:
                        strength_activities.append(activity)
                
                logger.info(f"Found {len(strength_activities)} strength training activities")
                if strength_activities:
                    return strength_activities
            else:
                logger.warning(f"Error with sports history endpoint: {response.status_code}")
        except Exception as e:
            logger.warning(f"Exception with sports history endpoint: {str(e)}")
        
        # Fallback: Try the activity types endpoint (GET)
        endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.ACTIVITY_TYPES_ENDPOINT}"
        logger.info(f"Trying activity types endpoint: {endpoint}")
        
        try:
            response = self._make_api_request('get', endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # Navigate the response structure to find strength activities
                logger.info(f"Got activity types response: {data}")
                # Analyze the response to see if we can extract activity information
            else:
                logger.warning(f"Error with activity types endpoint: {response.status_code}")
        except Exception as e:
            logger.warning(f"Exception with activity types endpoint: {str(e)}")
        
        # Last resort: Try the workout endpoint directly
        endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.WORKOUT_CREATE_ENDPOINT}"
        logger.info(f"Trying workout endpoint: {endpoint}")
        
        try:
            # In Charles transcript, this endpoint accepts GET with user_id parameter
            response = self._make_api_request('get', endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Got workout endpoint response: {data}")
                # Analyze the response to see if we can extract workout information
            else:
                logger.warning(f"Error with workout endpoint: {response.status_code}")
        except Exception as e:
            logger.warning(f"Exception with workout endpoint: {str(e)}")
        
        logger.error("Failed to retrieve strength activities after trying all observed endpoints")
        return []
    
    def _extract_activities_from_response(self, data):
        """
        Extract activities from a variety of response formats that might be returned
        by different Whoop API endpoints.
        
        Args:
            data: The parsed JSON response data
            
        Returns:
            list: Extracted activities
        """
        # Handle empty or None data
        if not data:
            return []
            
        activities = []
        
        try:
            # Handle different response formats
            if isinstance(data, dict):
                # Format 1: Dictionary with 'records' key
                if 'records' in data:
                    activities = data.get('records', [])
                # Format 2: Dictionary with 'data' key
                elif 'data' in data:
                    activities = data.get('data', [])
                # Format 3: Dictionary with 'activities' key
                elif 'activities' in data:
                    activities = data.get('activities', [])
                # Format 4: Dictionary with 'results' key
                elif 'results' in data:
                    activities = data.get('results', [])
                # Format 5: Single activity returned
                elif 'id' in data and ('sport_id' in data or 'type' in data):
                    activities = [data]
            # Format 6: Direct list of activities
            elif isinstance(data, list):
                activities = data
                
        except Exception as e:
            logger.warning(f"Error extracting activities from response: {str(e)}")
            
        return activities
    
    def _filter_strength_activities(self, activities):
        """
        Filter activities to only include strength training activities.
        Handles multiple different API formats for identifying activity types.
        
        Args:
            activities: List of activity data from API
            
        Returns:
            list: Filtered list of strength training activities
        """
        strength_activities = []
        
        for activity in activities:
            try:
                # Skip if not a dictionary
                if not isinstance(activity, dict):
                    continue
                    
                # Handle different API formats for activity type
                activity_type = None
                # Format 1: Direct sport_id field
                if 'sport_id' in activity:
                    activity_type = activity.get('sport_id')
                # Format 2: Nested sport object
                elif 'sport' in activity and isinstance(activity['sport'], dict):
                    activity_type = activity.get('sport', {}).get('id')
                    # Some APIs use 'name' instead of 'id'
                    if activity_type is None and 'name' in activity.get('sport', {}):
                        sport_name = activity.get('sport', {}).get('name', '').lower()
                        activity_type = 1 if 'strength' in sport_name else None
                # Format 3: Direct 'type' string field
                elif 'type' in activity:
                    activity_type_str = activity.get('type', '').lower()
                    activity_type = 1 if 'strength' in activity_type_str else None
                # Format 4: Workout type field
                elif 'workout_type' in activity:
                    workout_type = activity.get('workout_type', '').lower()
                    activity_type = 1 if 'strength' in workout_type else None
                    
                # Check if this is a strength training activity based on type detection
                is_strength = False
                
                # Check numeric sport ID (1 = Strength Training in Whoop's system)
                if activity_type == 1:
                    is_strength = True
                # Check string type identifiers
                elif isinstance(activity_type, str) and any(term in activity_type.lower() for term in ['strength', 'weight', 'resistance']):
                    is_strength = True
                # Check 'name' field for strength-related terms as backup
                elif 'name' in activity and isinstance(activity['name'], str) and any(term in activity['name'].lower() for term in ['strength', 'weight', 'resistance']):
                    is_strength = True
                    
                if is_strength:
                    strength_activities.append(activity)
                    
            except Exception as e:
                logger.warning(f"Error filtering activity: {str(e)}")
                continue
                
        return strength_activities
    
    def _save_successful_endpoint_config(self, base_url, endpoint_path, method, date_format, request_format):
        """
        Save the configuration that successfully retrieved activities to reuse in future calls
        and avoid unnecessary API calls to endpoints that don't work.
        
        This caches the successful endpoint within the current session.
        """
        # Update the active base URL and endpoint for future use
        self.UNOFFICIAL_BASE_URL = base_url
        self.ACTIVITY_SEARCH_ENDPOINT = endpoint_path
        
        # Log the successful configuration for debugging
        logger.info(f"Saved successful endpoint configuration:"
                   f"\n - Base URL: {base_url}"
                   f"\n - Endpoint: {endpoint_path}"
                   f"\n - Method: {method}"
                   f"\n - Date format: {date_format['format']}")
    
    def get_strength_workouts(self, days_ago=30):
        """
        Get strength training workouts from the last N days.
        
        Args:
            days_ago (int): Number of days to look back
            
        Returns:
            list: List of strength training workouts
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_ago)
        
        # Format dates for API call
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Add required headers based on captured traffic
        headers = {
            'Content-Type': 'application/json',
            'x-whoop-device-platform': 'API',
            'locale': 'en_US'
        }
        
        # Get workouts endpoint
        endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.WORKOUT_ENDPOINT}"
        
        # Add params for filtering
        params = {
            'start': start_date_str,
            'sport_id': 1,  # Strength Training
            'limit': 50
        }
        
        try:
            response = self.session.get(endpoint, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Error retrieving workouts: {response.status_code} - {response.text}")
                return []
                
            # Parse the response
            data = response.json()
            workouts = data.get('records', [])
            
            logger.info(f"Found {len(workouts)} strength training workouts")
            return workouts
        except Exception as e:
            logger.error(f"Error retrieving strength workouts: {str(e)}")
            return []
    
    def create_workout(self, start_time, end_time, sport_id=1, timezone=None):
        """
        Create a workout in Whoop using the unofficial API endpoint discovered from API traffic.
        
        Args:
            start_time (datetime): Start time of the workout
            end_time (datetime): End time of the workout
            sport_id (int): Sport ID (default 1 for Strength Training)
            timezone (str): Timezone string (e.g., 'America/Los_Angeles')
            
        Returns:
            dict: Created workout data or None if failed
        """
        self._ensure_authenticated()
        
        # Set up default timezone if not provided
        if timezone is None:
            timezone = 'America/Los_Angeles'  # Default timezone
        
        # Get timezone offset
        tz = pytz.timezone(timezone)
        offset = datetime.now(tz).strftime('%z')
        
        # Format the workout data based on captured API traffic
        workout_data = {
            "gpsEnabled": False,
            "timezoneOffset": offset,
            "sportId": sport_id,
            "source": "user",
            "during": {
                "lower": start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "upper": end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "bounds": "[)"
            }
        }
        
        # Add required headers based on captured traffic
        headers = {
            'Content-Type': 'application/json',
            'x-whoop-device-platform': 'API',
            'locale': 'en_US',
            'x-whoop-time-zone': timezone
        }
        
        # Create the workout
        workout_endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.WORKOUT_ENDPOINT}"
        
        try:
            logger.info(f"Creating workout from {start_time} to {end_time}")
            logger.debug(f"Workout data: {json.dumps(workout_data)}")
            
            # Use rate-limited request method
            response = self._make_api_request(
                'post',
                workout_endpoint, 
                json=workout_data,
                headers=headers
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                workout_id = data.get('id')
                logger.info(f"Successfully created Whoop workout: {workout_id}")
                return data
            elif response.status_code == 409:  # Conflict - workout already exists
                logger.warning("Workout already exists for this time period")
                response_data = response.json()
                logger.debug(f"Conflict response: {response_data}")
                
                # Check if we have overlap information
                overlaps = response_data.get('overlaps', [])
                if overlaps:
                    logger.info(f"Found {len(overlaps)} overlapping workouts")
                    return {'id': overlaps[0], 'status': 'existing'}
                return None
            elif response.status_code == 429:
                logger.warning("Rate limited when creating workout. Waiting before retrying...")
                time.sleep(random.uniform(5.0, 10.0))
                return None
            else:
                logger.error(f"Error creating workout: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Exception creating workout: {str(e)}")
            return None
    
    def link_workout_to_activity(self, activity_id, workout_data=None, name=None):
        """
        Link a strength training workout to an activity using the unofficial API.
        
        Args:
            activity_id (str): ID of the activity to link the workout to
            workout_data (dict): Dictionary containing exercises, sets, reps, etc.
            name (str): Optional name for the workout
            
        Returns:
            dict: Response data if successful, None otherwise
        """
        self._ensure_authenticated()
        
        if not activity_id:
            logger.error("Activity ID is required to link a workout")
            return None
            
        # Based on the API traffic analysis, we need to update the activity with workout metadata
        if workout_data is None:
            workout_data = {
                "exercises": []  # Default empty exercises list
            }
            
        # Add additional metadata if provided
        if name:
            workout_data["name"] = name
        
        # Add source information
        workout_data["source"] = "peloton"
        
        # Get the activity endpoint
        activity_endpoint = f"{self.UNOFFICIAL_BASE_URL}{self.ACTIVITY_ENDPOINT}/{activity_id}/workout"
        
        # Add required headers based on captured traffic
        headers = {
            'Content-Type': 'application/json',
            'x-whoop-device-platform': 'API',
            'locale': 'en_US'
        }
        
        try:
            logger.info(f"Linking workout to activity {activity_id}")
            logger.debug(f"Workout data: {json.dumps(workout_data)}")
            
            # Use rate-limited request method
            response = self._make_api_request(
                'post',
                activity_endpoint, 
                json=workout_data,
                headers=headers
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                logger.info(f"Successfully linked workout to activity {activity_id}")
                return data
            elif response.status_code == 429:
                logger.warning("Rate limited when linking workout to activity. Waiting before retrying...")
                time.sleep(random.uniform(5.0, 10.0))
                return None
            else:
                logger.error(f"Error linking workout to activity: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Exception linking workout to activity: {str(e)}")
            return None
