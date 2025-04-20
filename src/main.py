"""
Main entry point for the Peloton-to-Whoop integration.
"""

import os
import sys
import logging
import argparse
from datetime import datetime

from config import ConfigManager
from peloton_client import PelotonClient
from whoop_client import WhoopClient
from workout_sync import WorkoutSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sync.log'))
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description='Sync Peloton strength workouts to Whoop')
    parser.add_argument('--days', type=int, default=None,
                        help='Number of days in the past to sync (overrides config)')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config file (default: config.ini in project root)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run mode: no changes made to Whoop')
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        peloton_creds = config_manager.get_peloton_credentials()
        whoop_creds = config_manager.get_whoop_credentials()
        settings = config_manager.get_settings()
        
        # Override lookback days if specified in command line
        if args.days is not None:
            settings['lookback_days'] = args.days
        
        # Initialize clients
        logger.info("Initializing Peloton client")
        peloton_client = PelotonClient(peloton_creds['username'], peloton_creds['password'])
        authenticated = peloton_client.authenticate()
        if not authenticated:
            logger.error("Failed to authenticate with Peloton API")
            return 1
        
        logger.info("Initializing Whoop client")
        whoop_client = WhoopClient(whoop_creds)
        authenticated = whoop_client.authenticate()
        if not authenticated:
            logger.error("Failed to authenticate with Whoop API")
            return 1
        
        # Initialize workout synchronizer
        workout_sync = WorkoutSync(peloton_client, whoop_client, settings)
        
        # Execute sync
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made to Whoop")
            # In dry run mode, we'll just log what would happen
            # You could implement additional dry run logic here if needed
        else:
            logger.info(f"Starting workout sync for past {settings['lookback_days']} days")
            result = workout_sync.sync_workouts(days_ago=settings['lookback_days'])
            
            # Log results
            logger.info(f"Sync completed with status: {result.get('status')}")
            logger.info(f"Created {result.get('created_workouts')} new workouts")
            logger.info(f"Linked {result.get('linked_activities')} activities")
            
            if result.get('errors'):
                for error in result.get('errors'):
                    logger.error(f"Error during sync: {error}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
