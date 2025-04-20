# Product Requirements Document: Peloton-to-Whoop Strength Trainer Integration

## Overview
The Peloton-to-Whoop Strength Trainer Integration automates the transfer of strength training workout data from Peloton to Whoop. It identifies Peloton strength activities, extracts detailed movement data (exercises, reps, weights), and creates corresponding Workouts in Whoop, linking them to existing Strength Trainer activities.

## Problem Statement
When users complete strength training activities on Peloton, Whoop detects these workouts as "Strength Trainer" activities but lacks detailed information about the specific exercises performed. Currently, users must manually create Workouts in Whoop that describe the movements, rep counts, and weights used.

## Solution
An automated system that:
1. Retrieves strength training activity data from Peloton
2. Creates detailed Workouts in Whoop with exercise-specific information
3. Links these Workouts to the corresponding Strength Trainer activities in Whoop
4. Operates idempotently, ensuring no duplicate data creation

## User Requirements

### Authentication
- Users will provide their own Peloton and Whoop API credentials
- Credentials will never be stored in the repository or logged
- Secure credential storage using environment variables or a local configuration file ignored by git

### Core Functionality
1. **Data Retrieval from Peloton**
   - Access Peloton API to retrieve strength training activities
   - Extract detailed movement data (exercise names, reps, weights)

2. **Data Creation in Whoop**
   - Create Workouts in Whoop with detailed exercise information
   - Link Workouts to corresponding Strength Trainer activities based on timestamp proximity

3. **Idempotent Operation**
   - Check for existing Whoop Workouts before creating new ones
   - Verify existing links between Workouts and Strength Trainer activities
   - Add only missing links if a Workout already exists
   - Skip processing for already-linked Strength Trainer activities

4. **Activity Matching**
   - Match Peloton strength activities to Whoop Strength Trainer activities based on:
     - Date of activity
     - Time proximity
     - Duration similarity (if available)

### Technical Requirements
1. **Python Implementation**
   - Python 3.8+ compatibility
   - Virtual environment for dependency management
   - Requirements file for easy installation

2. **Code Structure**
   - Modular, maintainable code with clear separation of concerns
   - Comprehensive logging for troubleshooting
   - Error handling for API failures or data mismatches

3. **Security**
   - No hardcoding of credentials
   - No storing credentials in repository files
   - Secure handling of API tokens

4. **Documentation**
   - Clear setup instructions
   - Usage examples
   - Troubleshooting guide

## Success Criteria
1. Automated creation of Whoop Workouts from Peloton strength activities
2. Correct linking of Workouts to Strength Trainer activities
3. No duplicate data when run multiple times
4. Minimal user intervention required after initial setup

## Future Enhancements (Optional)
1. Scheduling capability for regular automatic synchronization
2. Web interface for monitoring synchronization status
3. Support for additional workout types beyond strength training
