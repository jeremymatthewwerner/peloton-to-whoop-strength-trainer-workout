# Peloton-to-Whoop Strength Trainer Integration

This tool automatically creates detailed Whoop Workouts from your Peloton strength training activities and links them to the corresponding Whoop Strength Trainer activities.

## Features

- Retrieves detailed movement data from Peloton strength activities (exercises, reps, weights)
- Creates corresponding Workouts in Whoop with exercise details
- Links Workouts to existing Strength Trainer activities in Whoop
- Runs idempotently - safe to run multiple times without creating duplicates
- Secure credential management - no API keys stored in the repository

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

# Run the integration
python src/main.py
```

## Security Note

This application requires your Peloton and Whoop API credentials. These credentials are:
- Never stored in the repository
- Only stored locally in your `config.ini` file (which is git-ignored)
- Never logged or transmitted anywhere

## Development

See the [Product Requirements Document](docs/PRD.md) for detailed specifications.

## License

MIT
