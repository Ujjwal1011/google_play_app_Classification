import time
import random
import json
import datetime
import os
import concurrent.futures
import copy
from google_play_scraper import app, search, exceptions
import requests.exceptions

# --- Default Scraper Configuration ---
SCRAPER_CONFIG = {
    'PROXY_FILE': 'good_proxies.txt',
    'OUTPUT_DIR': 'scraped_app_data', # Directory for raw JSON outputs
    'NUM_APPS_PER_CATEGORY': 200,
    'SEARCH_HITS_BUFFER': 30,
    'MAX_RETRIES_PER_OPERATION': 5,
    'INITIAL_BACKOFF_SECONDS': 6,
    'MAX_WORKERS_DETAILS': 18,
    'DELAY_BETWEEN_CATEGORIES': (10, 20),
    'DELAY_WITHIN_RETRY': (2, 5),
    'LANG': 'en',
    'COUNTRY': 'us',
    'PROXY_LIST': [] # Loaded dynamically
}

# === Utility Functions ===

def load_proxies(filename):
    """Loads proxies from a file, one per line."""
    try:
        with open(filename, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        if not proxies:
            print(f"Warning: Proxy file '{filename}' is empty.")
        else:
            print(f"Loaded {len(proxies)} proxies from '{filename}'.")
        return proxies
    except FileNotFoundError:
        print(f"Warning: Proxy file '{filename}' not found. Running without proxies.")
        return []

def set_proxy_env(proxy_ip_port):
    """Sets HTTP/HTTPS proxy environment variables. Clears them if None is passed."""
    if not proxy_ip_port:
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        return None
    proxy_url = f"http://{proxy_ip_port}"
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url
    return proxy_url

def json_datetime_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError (f"Type {type(obj)} not serializable")

def ensure_output_directory(dir_path):
    """Creates the output directory if it doesn't exist."""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            print(f"Created output directory: {dir_path}")
        except OSError as e:
            print(f"Error creating output directory '{dir_path}': {e}")
            return False
    return True

# === Core Scraping Functions ===

def search_apps_with_retry(search_term, num_apps_target, search_hits, config):
    """
    Fetches list of app IDs via search, retrying with different proxies on failure.
    Returns: list: A list of unique app IDs found, or an empty list on failure/no results.
    """
    proxy_list = config['PROXY_LIST']
    max_retries = config['MAX_RETRIES_PER_OPERATION']
    initial_backoff = config['INITIAL_BACKOFF_SECONDS']
    delay_within_retry = config['DELAY_WITHIN_RETRY']
    lang = config['LANG']
    country = config['COUNTRY']

    if not proxy_list: # Handle no proxy case first
        print(f"  Searching '{search_term}' without proxy.")
        try:
            set_proxy_env(None)
            results = search(query=search_term, n_hits=search_hits, lang=lang, country=country)
            if results:
                unique_ids = [item['appId'] for item in results if item.get('appId')]
                app_ids = list(dict.fromkeys(unique_ids))[:num_apps_target] # Unique & limit
                print(f"  [SUCCESS] Found {len(app_ids)} unique IDs for '{search_term}' directly.")
                return app_ids
            else:
                print(f"  [SUCCESS] Search for '{search_term}' direct returned 0 results.")
                return []
        except Exception as e:
            print(f"  [FAIL] Error searching '{search_term}' directly: {e}")
            return []

    # Proxies are available, proceed with retry logic
    tried_proxies = set()
    for attempt in range(max_retries):
        available_proxies = [p for p in proxy_list if p not in tried_proxies]
        if not available_proxies:
            print(f"  [FAIL] Search '{search_term}': No more available proxies after {attempt} attempts.")
            break

        current_proxy_ip_port = random.choice(available_proxies)
        tried_proxies.add(current_proxy_ip_port)
        proxy_url_used = set_proxy_env(current_proxy_ip_port)

        try:
            print(f"  [Attempt {attempt + 1}/{max_retries}] Searching '{search_term}' via Proxy: {proxy_url_used}")
            results = search(query=search_term, n_hits=search_hits, lang=lang, country=country)

            if results:
                unique_ids = [item['appId'] for item in results if item.get('appId')]
                app_ids = list(dict.fromkeys(unique_ids))[:num_apps_target] # Unique & limit
                print(f"  [SUCCESS] Found {len(app_ids)} unique IDs for '{search_term}' via {proxy_url_used} on attempt {attempt + 1}.")
                set_proxy_env(None) # Cleanup proxy env vars
                return app_ids
            else:
                print(f"  [SUCCESS] Search for '{search_term}' completed via {proxy_url_used} (attempt {attempt+1}) but found 0 results.")
                set_proxy_env(None) # Cleanup proxy env vars
                return []

        except exceptions.ExtraHTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'N/A'
            print(f"  [RETRY?] HTTP Error searching '{search_term}' (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): Status {status_code}")
            if status_code == 403:
                 print(f"  [FAIL] Received 403 searching '{search_term}'. Stopping retries for this search.")
                 break
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            print(f"  [RETRY?] Connection/Proxy Error searching '{search_term}' (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): {type(e).__name__}")
        except Exception as e:
            print(f"  [RETRY?] Unexpected Error searching '{search_term}' (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            wait_time = (initial_backoff * (2 ** attempt)) + random.uniform(delay_within_retry[0], delay_within_retry[1])
            print(f"          Waiting {wait_time:.2f} seconds before next search attempt...")
            time.sleep(wait_time)

    print(f"  [FAIL] Failed to complete search for '{search_term}' after {max_retries} attempts.")
    set_proxy_env(None) # Cleanup proxy env vars
    return []

def get_app_details_with_retry(app_id, config):
    """
    Fetches app details for a single app ID, retrying with different proxies.
    Returns: dict: The app details dictionary if successful, otherwise None.
    """
    proxy_list = config['PROXY_LIST']
    max_retries = config['MAX_RETRIES_PER_OPERATION']
    initial_backoff = config['INITIAL_BACKOFF_SECONDS']
    delay_within_retry = config['DELAY_WITHIN_RETRY']
    lang = config['LANG']
    country = config['COUNTRY']

    if not proxy_list:
        try:
            set_proxy_env(None)
            result = app(app_id, lang=lang, country=country)
            print(f"    [SUCCESS] Fetched {app_id} directly.")
            return result
        except exceptions.NotFoundError:
            print(f"    [FAIL] App {app_id} not found (direct).")
            return None
        except Exception as e:
            print(f"    [FAIL] Error fetching {app_id} directly: {e}")
            return None

    tried_proxies = set()
    for attempt in range(max_retries):
        available_proxies = [p for p in proxy_list if p not in tried_proxies]
        if not available_proxies:
            print(f"    [FAIL] {app_id}: No more available proxies after {attempt} attempts.")
            break

        current_proxy_ip_port = random.choice(available_proxies)
        tried_proxies.add(current_proxy_ip_port)
        proxy_url_used = set_proxy_env(current_proxy_ip_port)

        try:
            result = app(app_id, lang=lang, country=country)
            print(f"    [SUCCESS] Fetched {app_id} via {proxy_url_used} on attempt {attempt + 1}.")
            set_proxy_env(None) # Cleanup proxy env vars
            return result
        except exceptions.NotFoundError:
            print(f"    [FAIL] App {app_id} not found via {proxy_url_used}. No retry needed.")
            set_proxy_env(None) # Cleanup
            return None # Explicitly return None if app not found
        except exceptions.ExtraHTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'N/A'
            print(f"    [RETRY?] HTTP Error fetching {app_id} (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): Status {status_code}")
            if status_code == 403:
                 print(f"    [FAIL] Received 403 fetching {app_id} via {proxy_url_used}. Stopping retries.")
                 break
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            print(f"    [RETRY?] Connection/Proxy Error fetching {app_id} (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): {type(e).__name__}")
        except Exception as e:
            print(f"    [RETRY?] Unexpected Error fetching {app_id} (Proxy: {proxy_url_used}, Attempt: {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            wait_time = (initial_backoff * (2 ** attempt)) + random.uniform(delay_within_retry[0], delay_within_retry[1])
            time.sleep(wait_time)

    print(f"    [FAIL] Failed to fetch details for {app_id} after {max_retries} attempts.")
    set_proxy_env(None) # Cleanup proxy env vars
    return None

def fetch_multiple_app_details_parallel(app_ids, config):
    """
    Fetches details for a list of app IDs in parallel using ThreadPoolExecutor.
    Returns: list: A list of successfully fetched app detail dictionaries.
    """
    detailed_apps = []
    max_workers = config['MAX_WORKERS_DETAILS']
    max_retries = config['MAX_RETRIES_PER_OPERATION'] # For logging clarity

    if not app_ids:
        return []

    print(f"\n  Starting parallel detail fetching for {len(app_ids)} apps...")
    print(f"  Max Retries Per App: {max_retries} | Max Workers: {max_workers}")

    fetch_start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_appid = {
            executor.submit(get_app_details_with_retry, app_id, config): app_id
            for app_id in app_ids
        }

        successful_fetches = 0
        for future in concurrent.futures.as_completed(future_to_appid):
            app_id = future_to_appid[future]
            try:
                data = future.result()
                if data: # Check if data is not None
                    detailed_apps.append(data)
                    successful_fetches += 1
            except Exception as exc:
                print(f"    [ERROR] App ID {app_id} generated an unexpected exception during future execution: {exc}")

    fetch_end_time = time.time()
    print(f"\n  Finished parallel detail fetching in {fetch_end_time - fetch_start_time:.2f} seconds.")
    print(f"  Successfully fetched details for {successful_fetches} out of {len(app_ids)} app IDs.")
    return detailed_apps

def save_app_details(data, filename):
    """Saves the collected app details list to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=json_datetime_serializer)
        print(f"  Saved details for {len(data)} apps to '{filename}'")
        return True
    except Exception as e:
        print(f"  Error saving details to file '{filename}': {e}")
        return False

# === Main Scraper Orchestration Function ===

def scrape_categories(categories_dict, config):
    """
    Iterates through categories, searches, fetches details, saves to JSON files.

    Args:
        categories_dict (dict): Dictionary mapping category_id -> search_term.
        config (dict): The scraper configuration dictionary.

    Returns:
        list: A list of full paths to the JSON files created.
    """
    output_dir = config['OUTPUT_DIR']
    if not ensure_output_directory(output_dir):
        print("Exiting scraper due to directory creation error.")
        return []

    if not config.get('PROXY_LIST'): # Check if proxies were loaded into config
        print("\n" + "="*60)
        print("  SCRAPER WARNING: Running without proxies. Failures/blocks likely.")
        print("="*60 + "\n"); time.sleep(2)

    total_categories = len(categories_dict)
    processed_count = 0
    created_files = []

    for category_id, search_term in categories_dict.items():
        processed_count += 1
        safe_filename_base = category_id.replace('/', '_').replace('&', 'and').replace(' ', '_')
        # Output filename now includes the base directory
        category_filename = os.path.join(output_dir, f"{safe_filename_base}_details.json")

        print("\n" + "-"*50)
        print(f"Scraping Category {processed_count}/{total_categories}: ID '{category_id}', Search: '{search_term}'")
        print("-" * 50)

        category_start_time = time.time()

        if os.path.exists(category_filename):
            print(f"  Output file '{category_filename}' already exists. Skipping scraping.")
            created_files.append(category_filename) # Add existing file to the list
            continue

        # 1. Search for App IDs
        print(f"  Starting search...")
        app_ids_found = search_apps_with_retry(
            search_term,
            config['NUM_APPS_PER_CATEGORY'],
            config['NUM_APPS_PER_CATEGORY'] + config['SEARCH_HITS_BUFFER'],
            config
        )
        time.sleep(random.uniform(1, 3)) # Small delay after search batch

        # 2. Fetch App Details
        if app_ids_found:
            fetched_app_details = fetch_multiple_app_details_parallel(app_ids_found, config)

            # 3. Save Results
            if fetched_app_details:
                if save_app_details(fetched_app_details, category_filename):
                    created_files.append(category_filename) # Add newly created file
            else:
                print(f"  No app details successfully fetched for search term '{search_term}', no file saved.")
        else:
             print(f"  Skipping detail fetching as no app IDs were retrieved via search.")

        category_end_time = time.time()
        print(f"Category '{category_id}' scraping took {category_end_time - category_start_time:.2f} seconds.")

        # 4. Delay Between Categories
        if processed_count < total_categories:
             delay = random.uniform(config['DELAY_BETWEEN_CATEGORIES'][0], config['DELAY_BETWEEN_CATEGORIES'][1])
             print(f"\n--- Waiting for {delay:.2f} seconds before next category ---")
             time.sleep(delay)

    print("\n" + "="*50); print("--- Scraping Complete ---"); print("="*50)
    return created_files # Return list of files generated or found

# Example of how to run this module directly (optional)
if __name__ == "__main__":
    print("Running scraper module directly (for testing)...")
    # Load proxies into the default config
    SCRAPER_CONFIG['PROXY_LIST'] = load_proxies(SCRAPER_CONFIG['PROXY_FILE'])

    test_categories = {
        "Test_Shopping": "shopping app free",
        "Test_Games": "puzzle game offline"
    }
    # Reduce number of apps for testing
    test_config = SCRAPER_CONFIG.copy()
    test_config['NUM_APPS_PER_CATEGORY'] = 5
    test_config['SEARCH_HITS_BUFFER'] = 5
    test_config['DELAY_BETWEEN_CATEGORIES'] = (1, 2)

    generated_files = scrape_categories(test_categories, test_config)
    print("\nScraping test finished. Generated/found files:")
    for f in generated_files:
        print(f"- {f}")