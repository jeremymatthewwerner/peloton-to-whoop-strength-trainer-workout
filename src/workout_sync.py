"""
Synchronization logic between Peloton and Whoop platforms.
Handles matching activities and creating/linking workouts.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WorkoutSync:
    """
    Handles synchronization of workouts between Peloton and Whoop.
    """
    
    def __init__(self, peloton_client, whoop_client, settings):
        """
        Initialize the workout synchronizer.
        
        Args:
            peloton_client: Initialized Peloton API client
            whoop_client: Initialized Whoop API client
            settings: Dictionary of settings including time_threshold_minutes
        """
        self.peloton_client = peloton_client
        self.whoop_client = whoop_client
        self.settings = settings
        self.time_threshold_minutes = settings.get('time_threshold_minutes', 30)
    
    def sync_workouts(self, days_ago=30):
        """
        Synchronize strength workouts from Peloton to Whoop.
        
        Args:
            days_ago: Number of days in the past to synchronize
            
        Returns:
            dict: Summary of sync operation
        """
        logger.info(f"Starting workout sync for the past {days_ago} days")
        
        # Get Peloton strength workouts
        peloton_workouts = self.peloton_client.get_strength_workouts(days_ago=days_ago)
        if not peloton_workouts:
            logger.info("No Peloton strength workouts found to synchronize")
            return {
                'status': 'success', 
                'message': 'No Peloton strength workouts found to synchronize',
                'created_workouts': 0,
                'linked_activities': 0
            }
        
        logger.info(f"Found {len(peloton_workouts)} Peloton strength workouts")
        
        # Get Whoop strength trainer activities
        whoop_activities = self.whoop_client.get_strength_trainer_activities(days_ago=days_ago)
        if not whoop_activities:
            logger.info("No Whoop strength trainer activities found to link")
            return {
                'status': 'success', 
                'message': 'No Whoop strength trainer activities found to link',
                'created_workouts': 0,
                'linked_activities': 0
            }
        
        logger.info(f"Found {len(whoop_activities)} Whoop strength trainer activities")
        
        # Get existing Whoop workouts to avoid duplicates
        whoop_workouts = self.whoop_client.get_workouts(days_ago=days_ago)
        logger.info(f"Found {len(whoop_workouts)} existing Whoop workouts")
        
        # Track results
        created_workouts = 0
        linked_activities = 0
        errors = []
        
        # Process each Peloton workout
        for peloton_workout in peloton_workouts:
            try:
                # Get detailed workout info
                workout_id = peloton_workout.get('id')
                detailed_workout = self.peloton_client.get_strength_workout_details(workout_id)
                
                if not detailed_workout or not detailed_workout.get('exercises'):
                    logger.warning(f"Skipping workout {workout_id} - missing exercise data")
                    continue
                
                # Check if we already have a matching Whoop workout
                existing_workout = self._find_matching_workout(detailed_workout, whoop_workouts)
                
                # Match with corresponding Whoop activity
                whoop_activity = self._find_matching_activity(detailed_workout, whoop_activities)
                
                if not whoop_activity:
                    logger.warning(f"No matching Whoop activity found for Peloton workout {workout_id}")
                    continue
                
                # If we found a matching workout, link it
                if existing_workout:
                    logger.info(f"Found existing Whoop workout for Peloton workout {workout_id}")
                    workout_id_to_link = existing_workout.get('id')
                    
                    # Check if this activity is already linked to this workout
                    if self._is_activity_linked_to_workout(whoop_activity, workout_id_to_link):
                        logger.info(
                            f"Whoop activity {whoop_activity.get('id')} already linked to workout {workout_id_to_link}")
                        continue
                
                # Otherwise create a new workout
                else:
                    # Convert Peloton workout to Whoop workout format
                    whoop_workout_data = self._convert_to_whoop_workout(detailed_workout)
                    
                    # Create the workout in Whoop
                    created_workout = self.whoop_client.create_workout(whoop_workout_data)
                    
                    if not created_workout:
                        logger.error(f"Failed to create Whoop workout for Peloton workout {workout_id}")
                        errors.append(f"Failed to create Whoop workout for Peloton workout {workout_id}")
                        continue
                    
                    workout_id_to_link = created_workout.get('id')
                    created_workouts += 1
                    logger.info(f"Created Whoop workout {workout_id_to_link} for Peloton workout {workout_id}")
                
                # Link the workout to the activity
                link_success = self.whoop_client.link_workout_to_activity(
                    whoop_activity.get('id'), workout_id_to_link)
                
                if link_success:
                    linked_activities += 1
                    logger.info(
                        f"Linked Whoop workout {workout_id_to_link} to activity {whoop_activity.get('id')}")
                else:
                    errors.append(
                        f"Failed to link Whoop workout {workout_id_to_link} to activity {whoop_activity.get('id')}")
                
            except Exception as e:
                logger.error(f"Error processing Peloton workout {peloton_workout.get('id')}: {str(e)}")
                errors.append(f"Error processing Peloton workout {peloton_workout.get('id')}: {str(e)}")
        
        # Prepare result summary
        summary = {
            'status': 'success' if not errors else 'partial_success',
            'created_workouts': created_workouts,
            'linked_activities': linked_activities,
            'errors': errors if errors else None
        }
        
        return summary
    
    def _convert_to_whoop_workout(self, peloton_workout):
        """
        Convert a Peloton workout to Whoop workout format.
        
        Args:
            peloton_workout: Detailed Peloton workout data
            
        Returns:
            dict: Whoop workout data
        """
        # Extract basic workout information
        start_time = datetime.fromtimestamp(peloton_workout.get('start_time', 0))
        end_time = datetime.fromtimestamp(peloton_workout.get('end_time', 0))
        duration_seconds = peloton_workout.get('duration', 0)
        
        # Extract exercise information
        exercises = peloton_workout.get('exercises', [])
        
        # Format exercises for Whoop
        whoop_exercises = []
        for exercise in exercises:
            # Skip exercises with missing data
            if not exercise.get('name') or not exercise.get('reps'):
                continue
                
            whoop_exercise = {
                'name': exercise.get('name'),
                'reps': exercise.get('reps', 0),
                'sets': 1,  # Assuming 1 set per exercise in Peloton
                'weight': exercise.get('weight', 0),
                'weight_unit': exercise.get('weight_units', 'lbs')
            }
            whoop_exercises.append(whoop_exercise)
        
        # Create Whoop workout data
        whoop_workout = {
            'sport': 'Strength Training',
            'start_time': start_time.isoformat(),
            'duration': duration_seconds,
            'title': peloton_workout.get('title', 'Peloton Strength Training'),
            'exercises': whoop_exercises
        }
        
        return whoop_workout
    
    def _find_matching_activity(self, peloton_workout, whoop_activities):
        """
        Find a matching Whoop activity for a Peloton workout based on time proximity.
        
        Args:
            peloton_workout: Detailed Peloton workout data
            whoop_activities: List of Whoop activities
            
        Returns:
            dict: Matching Whoop activity or None if no match found
        """
        peloton_start_time = datetime.fromtimestamp(peloton_workout.get('start_time', 0))
        peloton_duration = peloton_workout.get('duration', 0)
        
        # Define time window for matching
        time_threshold = timedelta(minutes=self.time_threshold_minutes)
        
        best_match = None
        smallest_time_diff = None
        
        for activity in whoop_activities:
            # Check if the activity is already linked to a workout
            if activity.get('workout_id'):
                continue
                
            # Parse Whoop activity time
            whoop_time_str = activity.get('time_created', '')
            if not whoop_time_str:
                continue
                
            try:
                whoop_time = datetime.fromisoformat(whoop_time_str.replace('Z', '+00:00'))
                whoop_time = whoop_time.replace(tzinfo=None)  # Remove timezone info for comparison
                
                time_diff = abs((whoop_time - peloton_start_time).total_seconds())
                
                if time_diff <= time_threshold.total_seconds():
                    if smallest_time_diff is None or time_diff < smallest_time_diff:
                        smallest_time_diff = time_diff
                        best_match = activity
            except Exception as e:
                logger.error(f"Error parsing time for activity {activity.get('id')}: {str(e)}")
        
        return best_match
    
    def _find_matching_workout(self, peloton_workout, whoop_workouts):
        """
        Find if there is already a Whoop workout that matches this Peloton workout.
        
        Args:
            peloton_workout: Detailed Peloton workout data
            whoop_workouts: List of existing Whoop workouts
            
        Returns:
            dict: Matching Whoop workout or None if no match found
        """
        # Extract Peloton workout title and exercises
        peloton_title = peloton_workout.get('title', '')
        peloton_exercises = set(ex.get('name', '') for ex in peloton_workout.get('exercises', []) if ex.get('name'))
        
        if not peloton_exercises:
            return None
            
        # Look for matching workouts
        for workout in whoop_workouts:
            # Check if title contains Peloton
            if 'peloton' in workout.get('title', '').lower():
                # Check if exercises match
                whoop_exercises = set(ex.get('name', '') for ex in workout.get('exercises', []) if ex.get('name'))
                
                # If at least 70% of exercises match, consider it the same workout
                if whoop_exercises and peloton_exercises:
                    common_exercises = peloton_exercises.intersection(whoop_exercises)
                    similarity = len(common_exercises) / max(len(peloton_exercises), len(whoop_exercises))
                    
                    if similarity >= 0.7:
                        return workout
                        
        return None
    
    def _is_activity_linked_to_workout(self, activity, workout_id):
        """
        Check if an activity is already linked to the given workout.
        
        Args:
            activity: Whoop activity
            workout_id: Whoop workout ID
            
        Returns:
            bool: True if already linked, False otherwise
        """
        return activity.get('workout_id') == workout_id
