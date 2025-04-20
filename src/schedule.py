"""
Scheduling utilities for automatically running the Peloton-to-Whoop integration.
"""

import os
import sys
import time
import logging
import argparse
import schedule
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import main module
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from src.main import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(parent_dir, 'schedule.log'))
    ]
)

logger = logging.getLogger(__name__)

def run_sync():
    """Run the sync process and log any errors."""
    logger.info("Starting scheduled Peloton-to-Whoop sync")
    try:
        # Pass minimal set of arguments to main
        sys.argv = [sys.argv[0]]
        main()
        logger.info("Scheduled sync completed successfully")
    except Exception as e:
        logger.exception(f"Error in scheduled sync: {str(e)}")

def start_scheduler(interval_hours=12):
    """
    Start the scheduler to run the sync at specified intervals.
    
    Args:
        interval_hours: Hours between sync runs
    """
    logger.info(f"Starting scheduler with {interval_hours} hour interval")
    
    # Run once immediately
    run_sync()
    
    # Schedule regular runs
    schedule.every(interval_hours).hours.do(run_sync)
    
    # Keep the script running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Schedule Peloton-to-Whoop syncs')
    parser.add_argument('--interval', type=int, default=12,
                        help='Hours between sync runs (default: 12)')
    
    args = parser.parse_args()
    start_scheduler(args.interval)
