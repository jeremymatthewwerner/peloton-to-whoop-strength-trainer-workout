"""
Synchronization logic between Peloton and Whoop platforms.
Handles matching activities and creating/linking workouts.
"""

import logging
import pytz
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
        
        # Ensure time_threshold_minutes is an integer
        try:
            self.time_threshold_minutes = int(settings.get('time_threshold_minutes', 30))
        except (ValueError, TypeError):
            logger.warning(f"Invalid time_threshold_minutes value: {settings.get('time_threshold_minutes')}, using default 30")
            self.time_threshold_minutes = 30
            
        self.dry_run = False
        
    def set_dry_run_mode(self, enabled=True):
        """
        Enable or disable dry run mode. In dry run mode, no changes are made to Whoop.
        
        Args:
            enabled: Whether dry run mode is enabled
        """
        self.dry_run = enabled
        logger.info(f"Dry run mode {'enabled' if enabled else 'disabled'}")
    
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
        
        # Get Whoop strength trainer activities using our new method
        whoop_activities = self.whoop_client.find_strength_training_activities(days_ago=days_ago)
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
        whoop_workouts = self.whoop_client.get_strength_workouts(days_ago=days_ago)
        logger.info(f"Found {len(whoop_workouts)} existing Whoop workouts")
        
        # Track results
        created_workouts = 0
        linked_activities = 0
        errors = []
        
        # Process each Peloton workout
        for peloton_workout in peloton_workouts:
            try:
                # Get detailed workout info - with the updated client, we can get details directly
                detailed_workout = self.peloton_client.get_strength_workout_details(peloton_workout)
                
                # Debug log the workout structure
                workout_id = detailed_workout.get('id') if isinstance(detailed_workout, dict) else peloton_workout.get('id')
                logger.info(f"Processing Peloton workout {workout_id}")
                logger.info(f"Workout data keys: {list(detailed_workout.keys())}")
                logger.info(f"Duration value: {detailed_workout.get('duration')}, type: {type(detailed_workout.get('duration')).__name__}")
                
                if not detailed_workout or not detailed_workout.get('exercises'):
                    logger.warning(f"Skipping workout {workout_id} - missing exercise data")
                    continue
                
                workout_id = detailed_workout.get('id') if isinstance(detailed_workout, dict) else peloton_workout.get('id')

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
                    # Extract workout details from Peloton
                    start_time, end_time = self._extract_peloton_workout_times(detailed_workout)
                    
                    # Create the workout in Whoop (or simulate in dry run)
                    if self.dry_run:
                        # Simulate successful creation in dry run mode
                        workout_id_to_link = "dry-run-id-" + str(len(whoop_workouts) + created_workouts)
                        created_workouts += 1
                        logger.info(f"[DRY RUN] Would create Whoop workout for Peloton workout {workout_id}")
                    else:
                        # Use our new create_workout method with explicit start and end times
                        created_workout = self.whoop_client.create_workout(
                            start_time=start_time,
                            end_time=end_time,
                            sport_id=1  # 1 = Strength Training
                        )
                        
                        if not created_workout:
                            logger.error(f"Failed to create Whoop workout for Peloton workout {workout_id}")
                            errors.append(f"Failed to create Whoop workout for Peloton workout {workout_id}")
                            continue
                        
                        workout_id_to_link = created_workout.get('id')
                        created_workouts += 1
                        logger.info(f"Created Whoop workout {workout_id_to_link} for Peloton workout {workout_id}")
                
                # Prepare workout data for linking
                workout_data = self._create_workout_data_for_linking(detailed_workout)
                
                # Link the workout to the activity (or simulate in dry run)
                if self.dry_run:
                    linked_activities += 1
                    logger.info(f"[DRY RUN] Would link workout to Whoop activity {whoop_activity.get('id')}")
                else:
                    # Use our new method to link workout with the activity
                    link_success = self.whoop_client.link_workout_to_activity(
                        activity_id=whoop_activity.get('id'),
                        workout_data=workout_data,
                        name=detailed_workout.get('title', 'Peloton Strength Training')
                    )
                    
                    if link_success:
                        linked_activities += 1
                        logger.info(
                            f"Linked Whoop workout to activity {whoop_activity.get('id')}")
                    else:
                        errors.append(
                            f"Failed to link Whoop workout to activity {whoop_activity.get('id')}")
                
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
    
    def _extract_peloton_workout_times(self, peloton_workout):
        """
        Extract start and end times from a Peloton workout.
        
        Args:
            peloton_workout: Detailed Peloton workout data from the client
            
        Returns:
            tuple: (start_time, end_time) as datetime objects
        """
        # Extract start time
        start_time = peloton_workout.get('start_time', datetime.now())
        if not isinstance(start_time, datetime):
            # If somehow it's still a timestamp
            start_time = datetime.fromtimestamp(float(start_time)) if start_time else datetime.now()
            
        # Extract duration in seconds - ensure it's an integer
        duration_str = peloton_workout.get('duration', '0')
        
        try:
            # Handle various string formats and convert to integer
            if isinstance(duration_str, str):
                # Remove any non-numeric characters (except decimal point)
                duration_str = ''.join(c for c in duration_str if c.isdigit() or c == '.')
                duration_seconds = int(float(duration_str)) if duration_str else 1800
            else:
                # If it's already a number, just ensure it's an integer
                duration_seconds = int(float(duration_str)) if duration_str else 1800
        except (ValueError, TypeError):
            logger.warning(f"Invalid duration format: {duration_str}, using default 30 minutes")
            duration_seconds = 1800  # Default to 30 minutes
            
        # Sanity check on duration
        if duration_seconds < 60:  # Less than 1 minute doesn't make sense
            logger.warning(f"Duration too short ({duration_seconds} seconds), using default 30 minutes")
            duration_seconds = 1800  # Default to 30 minutes
            
        # Calculate end time
        end_time = start_time + timedelta(seconds=duration_seconds)
        logger.info(f"Extracted workout time range: {start_time} to {end_time} (duration: {duration_seconds} seconds)")
        
        return start_time, end_time
        
    def _create_workout_data_for_linking(self, peloton_workout):
        """
        Create workout data for linking to a Whoop activity.
        This formats the Peloton exercises in a way Whoop can understand.
        
        Args:
            peloton_workout: Detailed Peloton workout data
            
        Returns:
            dict: Formatted workout data for Whoop
        """
        # Extract exercise information
        exercises = peloton_workout.get('exercises', [])
        
        # Format exercises for Whoop
        whoop_exercises = []
        for exercise in exercises:
            # Skip exercises with missing data
            if not exercise.get('name'):
                continue
                
            reps = exercise.get('reps', 0)
            sets = exercise.get('sets', 1)
            weight = exercise.get('weight', 0)
            weight_unit = exercise.get('weight_unit', 'lbs') or 'lbs'
            
            whoop_exercise = {
                'name': exercise.get('name'),
                'reps': reps,
                'sets': sets,
                'weight': weight,
                'weight_unit': weight_unit
            }
            whoop_exercises.append(whoop_exercise)
        
        # Create workout data
        workout_data = {
            'exercises': whoop_exercises,
            'source': 'peloton',
            'name': peloton_workout.get('title', 'Peloton Strength Training')
        }
        
        return workout_data
    
    def _find_matching_activity(self, peloton_workout, whoop_activities):
        """
        Find a matching Whoop activity for a Peloton workout based on time proximity.
        
        Args:
            peloton_workout: Detailed Peloton workout data
            whoop_activities: List of Whoop activities
            
        Returns:
            dict: Matching Whoop activity or None if no match found
        """
        # Extract Peloton workout start time
        peloton_start_time = peloton_workout.get('start_time')
        if not isinstance(peloton_start_time, datetime):
            # If somehow it's still a timestamp
            peloton_start_time = datetime.fromtimestamp(peloton_start_time) if peloton_start_time else datetime.now()
        
        # Define time window for matching
        time_threshold = timedelta(minutes=self.time_threshold_minutes)
        
        best_match = None
        smallest_time_diff = None
        
        for activity in whoop_activities:
            # Check if the activity is already linked to a workout
            if activity.get('weightlifting_workout_id'):
                logger.debug(f"Activity {activity.get('id')} already has a linked workout")
                continue
            
            # Get start time from activity
            activity_time = None
            
            # Look in various fields for the time based on what we observed in the API traffic
            during = activity.get('during', '')
            if during:
                # Attempt to parse the time range from 'during' field
                try:
                    # Expected format: "['2025-04-15T14:35:08.000Z','2025-04-15T15:05:08.000Z')"
                    # Use regex to safely extract the date string
                    import re
                    match = re.search(r"'([^']+)'.*'([^']+)'\)", during)
                    
                    if match:
                        start_str = match.group(1)  # First captured group is the start time
                        # Convert ISO format to datetime
                        activity_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        logger.info(f"Parsed activity time: {activity_time} from string: {start_str}")
                    else:
                        logger.warning(f"Could not parse time range from: {during}")
                except Exception as e:
                    logger.warning(f"Error parsing activity time: {str(e)}")
                    # Fall back to other methods
                    pass
            
            # If we still don't have a time, try other fields
            if not activity_time:
                created_at = activity.get('created_at')
                if created_at:
                    try:
                        activity_time = datetime.fromisoformat(created_at.replace('Z', '+00:00').replace('+0000', '+00:00'))
                        activity_time = activity_time.replace(tzinfo=None)
                    except:
                        pass
            
            # If we still don't have a time, skip this activity
            if not activity_time:
                logger.debug(f"Could not parse time for activity {activity.get('id')}")
                continue
            
            # Compare times
            time_diff = abs((activity_time - peloton_start_time).total_seconds())
            logger.debug(f"Time difference for activity {activity.get('id')}: {time_diff} seconds")
            
            # Check if within threshold
            if time_diff <= time_threshold.total_seconds():
                if smallest_time_diff is None or time_diff < smallest_time_diff:
                    smallest_time_diff = time_diff
                    best_match = activity
                    logger.debug(f"Found better match: activity {activity.get('id')} with diff {time_diff} seconds")
        
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
