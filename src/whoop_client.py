"""
Whoop API client for retrieving and creating workout data.
"""

import logging
import requests
from datetime import datetime, timedelta
import json
import time

logger = logging.getLogger(__name__)

class WhoopClient:
    """Client for interacting with the Whoop API."""
    
    AUTH_URL = "https://api-7.whoop.com/oauth/token"
    BASE_URL = "https://api-7.whoop.com"
    
    def __init__(self, credentials):
        """
        Initialize the Whoop API client.
        
        Args:
            credentials: Dict containing either 'email' and 'password' or 'api_key'
        """
        self.credentials = credentials
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.authenticated = False
    
    def authenticate(self):
        """
        Authenticate with the Whoop API.
        
        Returns:
            bool: True if authentication was successful, False otherwise.
        """
        # If we already have an API key directly, skip authentication
        if 'api_key' in self.credentials and self.credentials['api_key']:
            self.token = self.credentials['api_key']
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
            
            # Get user ID to verify the token works
            try:
                user_info = self._get_user_info()
                self.user_id = user_info.get('id')
                if self.user_id:
                    self.authenticated = True
                    logger.info("Successfully authenticated with Whoop API using API key")
                    return True
                else:
                    logger.error("Failed to get user ID with provided API key")
                    return False
            except Exception as e:
                logger.error(f"Error authenticating with Whoop API key: {str(e)}")
                return False
        
        # Otherwise authenticate with username and password
        try:
            auth_payload = {
                'grant_type': 'password',
                'client_id': 'whoop_mobile_consumer',
                'username': self.credentials['email'],
                'password': self.credentials['password']
            }
            
            response = requests.post(self.AUTH_URL, json=auth_payload)
            response.raise_for_status()
            
            auth_data = response.json()
            self.token = auth_data.get('access_token')
            
            if not self.token:
                logger.error("Failed to get auth token from Whoop API")
                return False
            
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
            
            # Get the user ID
            user_info = self._get_user_info()
            self.user_id = user_info.get('id')
            
            if not self.user_id:
                logger.error("Failed to get user ID from Whoop API")
                return False
            
            self.authenticated = True
            logger.info("Successfully authenticated with Whoop API")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating with Whoop API: {str(e)}")
            return False
    
    def _ensure_authenticated(self):
        """Ensure the client is authenticated before making API calls."""
        if not self.authenticated:
            authenticated = self.authenticate()
            if not authenticated:
                raise RuntimeError("Failed to authenticate with Whoop API")
    
    def _get_user_info(self):
        """
        Get current user information.
        
        Returns:
            dict: User information
        """
        user_endpoint = f"{self.BASE_URL}/users/me"
        
        try:
            response = self.session.get(user_endpoint)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error retrieving user information: {str(e)}")
            return {}
    
    def get_activities(self, start_date, end_date=None):
        """
        Get activities between the specified dates.
        
        Args:
            start_date: Start date (datetime or ISO format string)
            end_date: End date (datetime or ISO format string), defaults to now if None
            
        Returns:
            list: Activities data
        """
        self._ensure_authenticated()
        
        # Format dates if they're datetime objects
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')
        
        activities_endpoint = f"{self.BASE_URL}/activities/feed"
        params = {
            'limit': 50,
            'start_date': start_date,
            'end_date': end_date
        }
        
        try:
            response = self.session.get(activities_endpoint, params=params)
            response.raise_for_status()
            
            activities_data = response.json()
            return activities_data.get('records', [])
            
        except Exception as e:
            logger.error(f"Error retrieving activities: {str(e)}")
            return []
    
    def get_strength_trainer_activities(self, days_ago=30):
        """
        Get Strength Trainer activities from the past specified days.
        
        Args:
            days_ago: Number of days in the past to retrieve activities for
            
        Returns:
            list: List of strength trainer activities
        """
        start_date = datetime.now() - timedelta(days=days_ago)
        all_activities = self.get_activities(start_date)
        
        # Filter for Strength Trainer activities
        strength_trainer_activities = [
            activity for activity in all_activities
            if activity.get('sport_id') == 1  # Strength Training sport_id
            and 'Strength Trainer' in activity.get('sport', {}).get('name', '')
        ]
        
        logger.info(f"Found {len(strength_trainer_activities)} Strength Trainer activities")
        return strength_trainer_activities
    
    def get_activity_detail(self, activity_id):
        """
        Get detailed information about a specific activity.
        
        Args:
            activity_id: ID of the activity to retrieve details for
            
        Returns:
            dict: Activity details
        """
        self._ensure_authenticated()
        
        detail_endpoint = f"{self.BASE_URL}/activities/{activity_id}"
        
        try:
            response = self.session.get(detail_endpoint)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error retrieving activity detail for {activity_id}: {str(e)}")
            return None
    
    def get_workouts(self, days_ago=30):
        """
        Get workouts from the past specified days.
        
        Args:
            days_ago: Number of days in the past to retrieve workouts for
            
        Returns:
            list: List of workouts
        """
        self._ensure_authenticated()
        
        start_date = datetime.now() - timedelta(days=days_ago)
        start_date_str = start_date.strftime('%Y-%m-%d')
        
        workouts_endpoint = f"{self.BASE_URL}/workouts"
        params = {
            'start_date': start_date_str
        }
        
        try:
            response = self.session.get(workouts_endpoint, params=params)
            response.raise_for_status()
            
            return response.json().get('records', [])
            
        except Exception as e:
            logger.error(f"Error retrieving workouts: {str(e)}")
            return []
    
    def create_workout(self, workout_data):
        """
        Create a new workout in Whoop.
        
        Args:
            workout_data: Dictionary containing workout details
            
        Returns:
            dict: Created workout data or None if creation failed
        """
        self._ensure_authenticated()
        
        workout_endpoint = f"{self.BASE_URL}/workouts"
        
        try:
            response = self.session.post(workout_endpoint, json=workout_data)
            response.raise_for_status()
            
            logger.info(f"Successfully created workout in Whoop")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error creating workout: {str(e)}")
            return None
    
    def link_workout_to_activity(self, activity_id, workout_id):
        """
        Link a workout to a Strength Trainer activity.
        
        Args:
            activity_id: ID of the Strength Trainer activity
            workout_id: ID of the workout to link
            
        Returns:
            bool: True if linking was successful, False otherwise
        """
        self._ensure_authenticated()
        
        link_endpoint = f"{self.BASE_URL}/activities/{activity_id}/workouts"
        payload = {
            'workout_id': workout_id
        }
        
        try:
            response = self.session.post(link_endpoint, json=payload)
            response.raise_for_status()
            
            logger.info(f"Successfully linked workout {workout_id} to activity {activity_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error linking workout to activity: {str(e)}")
            return False
