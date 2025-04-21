# Peloton-to-Whoop Strength Trainer Integration

This tool automatically creates detailed Whoop Workouts from your Peloton strength training activities and links them to the corresponding Whoop Strength Trainer activities.

## Features

- Retrieves detailed movement data from Peloton strength activities (exercises, reps, weights)
- Creates corresponding Workouts in Whoop with exercise details
- Links Workouts to existing Strength Trainer activities in Whoop
- Runs idempotently - safe to run multiple times without creating duplicates
- Secure credential management - no API keys stored in the repository
- Robust error handling and recovery for API interactions
- Enhanced API endpoint detection for better compatibility with Whoop updates
- Comprehensive time parsing for accurate workout matching

## API Implementation Note

This project uses the following APIs:

- **Peloton API**: Implemented using the community-maintained [peloton-client-library](https://github.com/geudrik/peloton-client-library) which provides a Python interface to Peloton's unofficial API.
- **Whoop API**: Our implementation is based on the reverse-engineered API endpoints from the [WhoopAPI-Wrapper](https://github.com/colinmacon/WhoopAPI-Wrapper) project.

Please note that neither Peloton nor Whoop provides official, public APIs. These implementations use reverse-engineered endpoints and may break if the underlying APIs change.

## Setup

1. Clone this repository
2. Set up the Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create a configuration file:
   ```bash
   cp config.example.ini config.ini
   ```
4. Edit `config.ini` with your Peloton and Whoop credentials

## Usage

```bash
# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Test your connection first
python src/test_connection.py

# Run the integration in dry-run mode (doesn't make changes)
python src/sync_runner.py --dry-run

# When you're ready, run the full integration
python src/sync_runner.py

# For daily automated use
python src/sync_yesterday.py
```

### Command Line Options

- `--days N`: Specify the number of days to look back for workouts (default: 30)
- `--dry-run`: Run in dry-run mode, no changes are made to your Whoop account
- `--config path/to/config.ini`: Specify a custom config file location
- `--verbose`: Enable detailed debug logging

## Security Note

This application requires your Peloton and Whoop API credentials. These credentials are:
- Never stored in the repository
- Only stored locally in your `config.ini` file (which is git-ignored)
- Never logged or transmitted anywhere

## Development

See the [Product Requirements Document](docs/PRD.md) for detailed specifications.

### API Traffic Analysis

If you encounter issues with API changes, see the [API Traffic Guide](docs/API_TRAFFIC_GUIDE.md) for instructions on using Charles Proxy to analyze and update API endpoints.

### Debugging Tools

The repository includes several debugging utilities:

- `src/test_connection.py`: Verifies authentication with both services
- `src/debug_activities.py`: Shows detailed information about recent activities
- `src/find_endpoints.py`: Helps identify working API endpoints
- `parse_charles.py`: Analyzes Charles Proxy export files to find API patterns

## License

MIT
