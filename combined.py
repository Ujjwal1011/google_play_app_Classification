import time
import os

# Import necessary functions and configs from other modules
from scraper import scrape_categories, load_proxies, SCRAPER_CONFIG
from model_analyzer import load_and_analyze_apps, ANALYZER_CONFIG
from evaluator import evaluate_results



# --- Main Workflow Function (Modified to accept categories_to_scrape) ---
def run_app_analysis_workflow_with_categories(categories_to_scrape=None, scraper_config_override=None, analyzer_config_override=None, evaluation_params_override=None):
    """
    Executes the full workflow: scraping, analyzing, and evaluating app data.
    Accepts categories_to_scrape and config overrides as arguments.
    Uses DEFAULT_CATEGORIES_TO_SCRAPE and default configs if no arguments provided.
    """
    DEFAULT_CATEGORIES_TO_SCRAPE = {}
    start_time = time.time()
    print("--- Starting Full Scrape, Analyze, Evaluate Workflow ---")

    # --- Step 1: Scraping ---
    print("\n--- Phase 1: Scraping App Data ---")
    scraper_config = SCRAPER_CONFIG.copy() # Start with default scraper config
    if scraper_config_override: # Apply overrides if provided
        scraper_config.update(scraper_config_override)
    scraper_config['PROXY_LIST'] = load_proxies(scraper_config['PROXY_FILE']) # Load proxies always

    categories = categories_to_scrape if categories_to_scrape else DEFAULT_CATEGORIES_TO_SCRAPE # Use provided or default categories

    scraped_json_files = scrape_categories(categories, scraper_config)

    if not scraped_json_files:
        print("\nScraping phase did not produce any files. Exiting scraping phase.")
        return
    else:
        print(f"\nScraping phase complete. Found/Generated {len(scraped_json_files)} JSON files.")

    # --- Step 2: LLM Analysis ---
    print("\n--- Phase 2: Analyzing Apps with LLM ---")
    analyzer_config = ANALYZER_CONFIG.copy() # Start with default analyzer config
    if analyzer_config_override: # Apply overrides
        analyzer_config.update(analyzer_config_override)

    if not analyzer_config.get('API_KEY'):
         print("CRITICAL ERROR: GEMINI_API_KEY environment variable not set. Analysis phase cannot proceed.")
         return

    load_and_analyze_apps(scraped_json_files, analyzer_config)
    analysis_csv_file = analyzer_config['CSV_FILE']
    print(f"\nAnalysis phase complete. Results should be in '{analysis_csv_file}'.")
    time.sleep(4)

    # --- Step 3: Evaluation ---
    print("\n--- Phase 3: Evaluating Analysis Results ---")
    if not os.path.exists(analysis_csv_file):
        print(f"Evaluation phase skipped: Analysis CSV file '{analysis_csv_file}' not found.")
    else:
        evaluation_params = evaluation_params_override if evaluation_params_override else {} # Use overrides or empty dict
        evaluated_df = evaluate_results(analysis_csv_file, **evaluation_params)

        if evaluated_df is not None:
            print("\nEvaluation phase complete.")
        else:
            print("\nEvaluation phase failed or produced no results.")
    
    # --- Workflow End ---
    end_time = time.time()
    print("\n--- Full Workflow Finished ---")
    print(f"Total execution time: {end_time - start_time:.2f} seconds")
    print(f"Final output saved to CSV file.'{analysis_csv_file}'")
    





# --- New Function for Analyzing and Evaluating JSON Files ---
def analyze_and_evaluate_json_files(json_file_list, analyzer_config_override=None, evaluation_params_override=None):
    """
    Analyzes and evaluates a list of pre-existing JSON files.
    Skips the scraping phase.

    Args:
        json_file_list (list): List of paths to JSON files containing app data.
        analyzer_config_override (dict, optional): Overrides for analyzer configuration. Defaults to None.
        evaluation_params_override (dict, optional): Overrides for evaluation parameters. Defaults to None.
    """
    start_time = time.time()
    print("--- Starting Analyze and Evaluate JSON Files Workflow ---")

    # --- Step 1: Skip Scraping (using provided JSON files) ---
    print("\n--- Phase 1: Using Provided JSON Files (Skipping Scraping) ---")
    if not json_file_list:
        print("Error: No JSON files provided for analysis. Exiting.")
        return
    print(f"Using provided JSON files for analysis: {json_file_list}")
    scraped_json_files = json_file_list # Use the provided list

    # --- Step 2: LLM Analysis ---
    print("\n--- Phase 2: Analyzing Apps with LLM ---")
    analyzer_config = ANALYZER_CONFIG.copy() # Start with default analyzer config
    if analyzer_config_override: # Apply overrides
        analyzer_config.update(analyzer_config_override)

    if not analyzer_config.get('API_KEY'):
         print("CRITICAL ERROR: GEMINI_API_KEY environment variable not set. Analysis phase cannot proceed.")
         return

    load_and_analyze_apps(scraped_json_files, analyzer_config)
    analysis_csv_file = analyzer_config['CSV_FILE'] # Get the CSV path used by the analyzer
    print(f"\nAnalysis phase complete. Results should be in '{analysis_csv_file}'.")
    time.sleep(4)

    # --- Step 3: Evaluation ---
    print("\n--- Phase 3: Evaluating Analysis Results ---")
    if not os.path.exists(analysis_csv_file):
        print(f"Evaluation phase skipped: Analysis CSV file '{analysis_csv_file}' not found.")
    else:
        evaluation_params = evaluation_params_override if evaluation_params_override else {} # Use overrides or empty dict
        evaluated_df = evaluate_results(analysis_csv_file, **evaluation_params)

        if evaluated_df is not None:
            print("\nEvaluation phase complete.")
        else:
            print("\nEvaluation phase failed or produced no results.")

    # --- Workflow End ---
    end_time = time.time()
    print("\n--- Analyze and Evaluate JSON Files Workflow Finished ---")
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

