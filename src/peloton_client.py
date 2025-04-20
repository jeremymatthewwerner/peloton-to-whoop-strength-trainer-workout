"""
Peloton API client for retrieving workout and strength training data.
"""

import logging
import requests
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class PelotonClient:
    """Client for interacting with the Peloton API."""
    
    BASE_URL = "https://api.onepeloton.com"
    
    def __init__(self, username, password):
        """
        Initialize the Peloton API client.
        
        Args:
            username: Peloton account username
            password: Peloton account password
        """
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.user_id = None
        self.session_id = None
        self.authenticated = False
    
    def authenticate(self):
        """
        Authenticate with the Peloton API.
        
        Returns:
            bool: True if authentication was successful, False otherwise.
        """
        auth_endpoint = f"{self.BASE_URL}/auth/login"
        payload = {
            "username_or_email": self.username,
            "password": self.password
        }
        
        try:
            response = self.session.post(auth_endpoint, json=payload)
            response.raise_for_status()
            
            auth_data = response.json()
            self.user_id = auth_data["user_id"]
            self.session_id = auth_data["session_id"]
            self.session.headers.update({
                "Cookie": f"peloton_session_id={self.session_id}",
                "Content-Type": "application/json"
            })
            self.authenticated = True
            logger.info("Successfully authenticated with Peloton API")
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Authentication failed: {e}")
            if response.status_code == 401:
                logger.error("Invalid credentials")
            return False
        except Exception as e:
            logger.error(f"Error authenticating with Peloton: {str(e)}")
            return False
    
    def _ensure_authenticated(self):
        """Ensure the client is authenticated before making API calls."""
        if not self.authenticated:
            authenticated = self.authenticate()
            if not authenticated:
                raise RuntimeError("Failed to authenticate with Peloton API")
    
    def get_workouts(self, days_ago=30, limit=50):
        """
        Get recent workouts from Peloton.
        
        Args:
            days_ago: Number of days in the past to retrieve workouts for
            limit: Maximum number of workouts to retrieve
            
        Returns:
            list: List of workout data dictionaries
        """
        self._ensure_authenticated()
        
        workouts_endpoint = f"{self.BASE_URL}/api/user/{self.user_id}/workouts"
        
        start_date = datetime.now() - timedelta(days=days_ago)
        start_timestamp = int(start_date.timestamp())
        
        params = {
            "joins": "ride,ride.instructor",
            "limit": limit,
            "page": 0,
            "sort_by": "-created"
        }
        
        try:
            response = self.session.get(workouts_endpoint, params=params)
            response.raise_for_status()
            
            data = response.json()
            workouts = data["data"]
            
            # Filter workouts by date
            filtered_workouts = [
                workout for workout in workouts 
                if workout["created_at"] >= start_timestamp
            ]
            
            logger.info(f"Retrieved {len(filtered_workouts)} workouts from Peloton")
            return filtered_workouts
            
        except Exception as e:
            logger.error(f"Error retrieving workouts: {str(e)}")
            return []
    
    def get_strength_workouts(self, days_ago=30):
        """
        Get strength training workouts from Peloton.
        
        Args:
            days_ago: Number of days in the past to retrieve workouts for
            
        Returns:
            list: List of strength workout data dictionaries
        """
        all_workouts = self.get_workouts(days_ago=days_ago)
        
        # Filter for strength workouts
        strength_workouts = [
            workout for workout in all_workouts
            if workout.get("fitness_discipline") == "strength"
        ]
        
        logger.info(f"Found {len(strength_workouts)} strength workouts")
        return strength_workouts
    
    def get_workout_details(self, workout_id):
        """
        Get detailed information about a specific workout.
        
        Args:
            workout_id: ID of the workout to retrieve details for
            
        Returns:
            dict: Workout details dictionary
        """
        self._ensure_authenticated()
        
        details_endpoint = f"{self.BASE_URL}/api/workout/{workout_id}"
        
        try:
            response = self.session.get(details_endpoint)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error retrieving workout details for {workout_id}: {str(e)}")
            return None
    
    def get_workout_performance(self, workout_id):
        """
        Get performance metrics for a specific workout.
        
        Args:
            workout_id: ID of the workout to retrieve performance data for
            
        Returns:
            dict: Performance metrics dictionary
        """
        self._ensure_authenticated()
        
        performance_endpoint = f"{self.BASE_URL}/api/workout/{workout_id}/performance_graph"
        
        try:
            response = self.session.get(performance_endpoint)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error retrieving performance data for {workout_id}: {str(e)}")
            return None
    
    def get_strength_workout_details(self, workout_id):
        """
        Get comprehensive strength workout details including movements,
        reps, and weights.
        
        Args:
            workout_id: ID of the strength workout
            
        Returns:
            dict: Dictionary with workout details and exercises
        """
        workout_details = self.get_workout_details(workout_id)
        if not workout_details:
            return None
        
        performance_data = self.get_workout_performance(workout_id)
        if not performance_data:
            return workout_details  # Return what we have even if performance data is missing
        
        # Extract exercises, reps, and weights from the performance data
        exercises = []
        
        try:
            segments = performance_data.get('segment_list', [])
            for segment in segments:
                metrics = segment.get('metrics', {})
                
                if 'name' not in segment:
                    continue  # Skip segments without names
                
                exercise = {
                    'name': segment.get('name', 'Unknown Exercise'),
                    'id': segment.get('id'),
                    'duration': segment.get('length', 0),
                    'reps': None,
                    'weight': None,
                    'weight_units': 'lbs'  # Assuming default weight unit
                }
                
                # Extract reps and weights if available
                for metric in metrics.values():
                    if metric.get('slug') == 'count' or metric.get('display_name', '').lower() == 'reps':
                        exercise['reps'] = metric.get('value', 0)
                    elif metric.get('slug') == 'total_weight' or 'weight' in metric.get('display_name', '').lower():
                        exercise['weight'] = metric.get('value', 0)
                
                exercises.append(exercise)
        
        except Exception as e:
            logger.error(f"Error parsing exercise data for workout {workout_id}: {str(e)}")
        
        # Add exercises to the workout details
        workout_details['exercises'] = exercises
        
        return workout_details
