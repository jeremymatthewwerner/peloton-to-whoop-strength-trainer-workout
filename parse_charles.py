#!/usr/bin/env python3
"""
Parse the Charles proxy session file to extract Whoop API patterns.

This enhanced version provides more detailed analysis of Whoop API traffic patterns
including host, path, and query parameter distribution to help identify
the most current API endpoints for different operations.

Usage:
  python parse_charles.py [whoop_charles_file.chlsj]

If no file is specified, it will try to use 'whoop_strength.chlsj' by default.
"""

import json
import sys
import os
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs
from datetime import datetime

def print_headers(headers_list, search_key=None, print_all=False):
    """Print formatted headers from a list of header dictionaries"""
    if not headers_list:
        return
    
    auth_headers = []
    other_headers = []
    
    for header in headers_list:
        name = header.get('name', '').lower()
        value = header.get('value', '')
        
        if not name or not value:
            continue
            
        # If searching for specific header
        if search_key and search_key.lower() in name:
            print(f"    {header.get('name')}: {value[:100]}{'...' if len(value) > 100 else ''}")
            continue
            
        # Categorize headers
        if name in ('authorization', 'x-whoop-token', 'x-api-key', 'x-amz-security-token'):
            auth_headers.append((header.get('name'), value))
        elif print_all:
            other_headers.append((header.get('name'), value))
    
    # Print auth headers first
    for name, value in auth_headers:
        print(f"    {name}: {value[:50]}{'...' if len(value) > 50 else ''}")
    
    # Print other headers if requested
    if print_all:
        for name, value in other_headers:
            print(f"    {name}: {value[:50]}{'...' if len(value) > 50 else ''}")

def print_body(body_data, truncate=True, indent=2):
    """Print body data that might be string or dictionary"""
    if not body_data:
        print("    [Empty body]")
        return
        
    if isinstance(body_data, dict):
        print(f"    {json.dumps(body_data, indent=indent)[:500]}{'...' if truncate and len(json.dumps(body_data)) > 500 else ''}")
    elif isinstance(body_data, str):
        try:
            # Try to parse as JSON
            json_data = json.loads(body_data)
            print(f"    {json.dumps(json_data, indent=indent)[:500]}{'...' if truncate and len(body_data) > 500 else ''}")
        except json.JSONDecodeError:
            # Not JSON, print as string
            print(f"    {body_data[:200]}{'...' if truncate and len(body_data) > 200 else ''}")
    else:
        print(f"    [Body is {type(body_data).__name__}, not printable]")

def extract_request_patterns(requests):
    """Extract and analyze patterns from the requests"""
    hosts = Counter()
    paths = Counter()
    methods = Counter()
    endpoints = defaultdict(lambda: defaultdict(int))
    activity_endpoints = []
    workout_endpoints = []
    status_codes = Counter()
    param_patterns = defaultdict(set)
    auth_headers = set()
    
    # Regular expressions to find date formats in parameters
    date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
    
    for req in requests:
        host = req.get('host', '')
        path = req.get('path', '')
        method = req.get('method', '')
        query = req.get('query', '')
        status = req.get('status_code', 0)
        
        # Update counters
        hosts[host] += 1
        paths[path] += 1
        methods[method] += 1
        status_codes[status] += 1
        
        # Track host+path combinations
        endpoints[host][path] += 1
        
        # Track date formats in parameters
        if query:
            parsed_query = parse_qs(query)
            for param, values in parsed_query.items():
                for value in values:
                    param_patterns[param].add(value[:20] + ('...' if len(value) > 20 else ''))
        
        # Extract request body patterns if present
        if 'request' in req and 'body' in req['request']:
            body = req['request'].get('body')
            if isinstance(body, str):
                try:
                    body_json = json.loads(body)
                    if isinstance(body_json, dict):
                        for key in body_json:
                            param_patterns[f"body:{key}"].add(str(type(body_json[key]).__name__))
                            
                            # Extract date patterns
                            if isinstance(body_json[key], str) and date_pattern.search(body_json[key]):
                                param_patterns["date_formats"].add(body_json[key])
                except:
                    pass
        
        # Extract auth headers
        if 'request' in req and 'header' in req['request'] and 'headers' in req['request']['header']:
            for header in req['request']['header']['headers']:
                if header.get('name', '').lower() == 'authorization':
                    value = header.get('value', '')
                    if value.startswith('Bearer '):
                        auth_headers.add(value[7:15] + '...')
        
        # Find activity and workout-related endpoints
        if 'activit' in path.lower():
            activity_endpoints.append((method, host, path, status))
        if 'workout' in path.lower():
            workout_endpoints.append((method, host, path, status))
    
    return {
        'hosts': hosts,
        'paths': paths,
        'methods': methods,
        'endpoints': endpoints,
        'activity_endpoints': activity_endpoints,
        'workout_endpoints': workout_endpoints,
        'status_codes': status_codes,
        'param_patterns': param_patterns,
        'auth_headers': auth_headers
    }

def main():
    try:
        # Get filename from command line args or use default
        filename = sys.argv[1] if len(sys.argv) > 1 else 'whoop_strength.chlsj'
        
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found")
            print("Please provide a valid Charles session file (.chlsj)")
            return 1
        
        # Load the Charles session file
        with open(filename, 'r') as f:
            data = json.load(f)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=== WHOOP API PATTERN ANALYSIS ({timestamp}) ===")
        print(f"File: {filename}")
        print(f"Loaded {len(data)} requests from Charles session")
        
        # Filter for Whoop-related requests
        whoop_requests = [req for req in data if any(whoop_domain in req.get('host', '').lower() 
                                                   for whoop_domain in ['whoop', 'api-7', 'app.whoop'])]
        print(f"Found {len(whoop_requests)} Whoop-related requests")
        
        if not whoop_requests:
            print("No Whoop-related requests found in the session file.")
            print("Please capture API traffic from the Whoop mobile app or website.")
            return 0
            
        # Extract patterns from the requests
        patterns = extract_request_patterns(whoop_requests)
        
        # Print host distribution
        print("\n=== API HOST DISTRIBUTION ===")
        for host, count in patterns['hosts'].most_common():
            print(f"{host}: {count} requests")
        
        # Print method distribution
        print("\n=== HTTP METHOD DISTRIBUTION ===")
        for method, count in patterns['methods'].most_common():
            print(f"{method}: {count} requests")
            
        # Print status code distribution
        print("\n=== STATUS CODE DISTRIBUTION ===")
        for status, count in patterns['status_codes'].most_common():
            print(f"{status}: {count} responses")
        
        # Print authentication-related endpoints
        auth_endpoints = []
        for req in whoop_requests:
            path = req.get('path', '').lower()
            if any(term in path for term in ['oauth', 'token', 'login', 'auth', 'user']):
                auth_endpoints.append((req.get('method'), req.get('host'), req.get('path')))
        
        print("\n=== AUTHENTICATION ENDPOINTS ===")
        for i, (method, host, path) in enumerate(sorted(set(auth_endpoints))):
            print(f"{i+1}. {method} https://{host}{path}")
        
        # Print activity-related endpoints
        print("\n=== ACTIVITY ENDPOINTS ===")
        activity_endpoints = patterns['activity_endpoints']
        unique_activity_endpoints = set([(m, h, p) for m, h, p, _ in activity_endpoints])
        
        for i, (method, host, path) in enumerate(sorted(unique_activity_endpoints)):
            # Count success rate for this endpoint
            success_count = sum(1 for m, h, p, s in activity_endpoints 
                              if m == method and h == host and p == path and s in [200, 201, 204])
            total_count = sum(1 for m, h, p, _ in activity_endpoints 
                             if m == method and h == host and p == path)
            
            success_rate = (success_count / total_count * 100) if total_count > 0 else 0
            print(f"{i+1}. {method} https://{host}{path} - {success_count}/{total_count} successful ({success_rate:.1f}%)")
        
        # Print workout-related endpoints
        print("\n=== WORKOUT ENDPOINTS ===")
        workout_endpoints = patterns['workout_endpoints']
        unique_workout_endpoints = set([(m, h, p) for m, h, p, _ in workout_endpoints])
        
        for i, (method, host, path) in enumerate(sorted(unique_workout_endpoints)):
            # Count success rate for this endpoint
            success_count = sum(1 for m, h, p, s in workout_endpoints 
                              if m == method and h == host and p == path and s in [200, 201, 204])
            total_count = sum(1 for m, h, p, _ in workout_endpoints 
                             if m == method and h == host and p == path)
            
            success_rate = (success_count / total_count * 100) if total_count > 0 else 0
            print(f"{i+1}. {method} https://{host}{path} - {success_count}/{total_count} successful ({success_rate:.1f}%)")
        
        # Print common request parameter patterns
        print("\n=== COMMON REQUEST PARAMETERS ===")
        params_to_show = ['during', 'sport_id', 'sport_ids', 'limit', 'startTime', 'endTime', 'from', 'to']
        for param in params_to_show:
            if param in patterns['param_patterns'] or f"body:{param}" in patterns['param_patterns']:
                print(f"\n{param}:")
                if param in patterns['param_patterns']:
                    for pattern in patterns['param_patterns'][param]:
                        print(f"  - {pattern}")
                if f"body:{param}" in patterns['param_patterns']:
                    for pattern in patterns['param_patterns'][f"body:{param}"]:
                        print(f"  - (in body) {pattern}")
        
        # Print date format patterns found in requests
        if "date_formats" in patterns['param_patterns']:
            print("\n=== DATE FORMAT PATTERNS ===")
            for pattern in patterns['param_patterns']["date_formats"]:
                print(f"  {pattern}")
        
        # Print a summary of API structure
        print("\n=== API STRUCTURE SUMMARY ===")
        print("Based on the API traffic analysis, the following pattern was detected:")
        
        # Detect API patterns
        main_hosts = [host for host, count in patterns['hosts'].most_common(2)]
        print(f"\nMain API hosts: {', '.join(main_hosts)}")
        
        # Print the most successful activity API endpoints
        successful_activity_endpoints = []
        for method, host, path, status in activity_endpoints:
            if status in [200, 201, 204]:
                successful_activity_endpoints.append((method, host, path))
        
        print("\nMost successful activity endpoints:")
        activity_counters = Counter(successful_activity_endpoints)
        for (method, host, path), count in activity_counters.most_common(3):
            print(f"  {method} https://{host}{path} ({count} successful requests)")
        
        # Print the most successful workout API endpoints
        successful_workout_endpoints = []
        for method, host, path, status in workout_endpoints:
            if status in [200, 201, 204]:
                successful_workout_endpoints.append((method, host, path))
        
        print("\nMost successful workout endpoints:")
        workout_counters = Counter(successful_workout_endpoints)
        for (method, host, path), count in workout_counters.most_common(3):
            print(f"  {method} https://{host}{path} ({count} successful requests)")
        
        # Extract and show sample requests with their details
        print("\n=== SAMPLE API CALLS (FOR IMPLEMENTATION) ===")
        
        # Find a successful activity endpoint call
        sample_activity_req = None
        for req in whoop_requests:
            if 'activit' in req.get('path', '').lower() and req.get('status_code') in [200, 201]:
                sample_activity_req = req
                break
        
        if sample_activity_req:
            print("\nSample Activity API Call:")
            method = sample_activity_req.get('method')
            host = sample_activity_req.get('host')
            path = sample_activity_req.get('path')
            print(f"{method} https://{host}{path}")
            
            # Print request headers
            if sample_activity_req.get('request', {}).get('header', {}).get('headers'):
                print("Request Headers:")
                print_headers(sample_activity_req.get('request', {}).get('header', {}).get('headers'), print_all=True)
            
            # Print request body
            if sample_activity_req.get('request', {}).get('body'):
                print("Request Body:")
                print_body(sample_activity_req.get('request', {}).get('body'), truncate=False)
            
            # Print response body
            if sample_activity_req.get('response', {}).get('body'):
                print("Response Body:")
                print_body(sample_activity_req.get('response', {}).get('body'), truncate=False)
        
        # Find a successful workout endpoint call
        sample_workout_req = None
        for req in whoop_requests:
            if 'workout' in req.get('path', '').lower() and req.get('status_code') in [200, 201]:
                sample_workout_req = req
                break
        
        if sample_workout_req:
            print("\nSample Workout API Call:")
            method = sample_workout_req.get('method')
            host = sample_workout_req.get('host')
            path = sample_workout_req.get('path')
            print(f"{method} https://{host}{path}")
            
            # Print request headers
            if sample_workout_req.get('request', {}).get('header', {}).get('headers'):
                print("Request Headers:")
                print_headers(sample_workout_req.get('request', {}).get('header', {}).get('headers'), print_all=True)
            
            # Print request body
            if sample_workout_req.get('request', {}).get('body'):
                print("Request Body:")
                print_body(sample_workout_req.get('request', {}).get('body'), truncate=False)
            
            # Print response body
            if sample_workout_req.get('response', {}).get('body'):
                print("Response Body:")
                print_body(sample_workout_req.get('response', {}).get('body'), truncate=False)
        
        # Print configuration recommendations
        print("\n=== RECOMMENDED WHOOP CLIENT CONFIGURATION ===")
        print("Based on the API traffic analysis, we recommend the following configuration:")
        
        # Suggest base URLs
        print("\n# Base URLs")
        print("UNOFFICIAL_BASE_URLS = [")
        for host, count in patterns['hosts'].most_common():
            print(f"    \"https://{host}\",")
        print("]")
        
        # Suggest activity endpoints
        print("\n# Activity endpoints")
        print("ACTIVITY_ENDPOINTS = [")
        for (method, host, path), count in activity_counters.most_common(5):
            print(f"    (\"{path}\", \"{method}\"),")
        print("]")
        
        # Suggest workout endpoints
        print("\n# Workout endpoints")
        print("WORKOUT_ENDPOINTS = [")
        for (method, host, path), count in workout_counters.most_common(5):
            print(f"    (\"{path}\", \"{method}\"),")
        print("]")
        
        return 0
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
