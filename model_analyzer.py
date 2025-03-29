from dotenv import load_dotenv
import os
import google.generativeai as genai  # Corrected import
import json
import csv
import time
import logging
import chardet
import datetime

load_dotenv()

# --- Default Analyzer Configuration ---
ANALYZER_CONFIG = {
    'API_KEY': os.environ.get("GEMINI_API_KEY"),
    'MODEL_NAME': "gemini-1.5-flash-latest",  # Keep the model name config
    'CSV_FILE': 'app_analysis_results.csv',
    'LLM_RETRY_DELAY': 3,
    'REASON_CHAR_LIMIT': 300
}

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- LLM Integration ---
def get_gemini_client(api_key):
    """Initializes and returns the Gemini client using genai.GenerativeModel."""
    if not api_key:
        logging.error("GEMINI_API_KEY environment variable not set.")
        raise ValueError("API Key for Gemini not configured.")
    try:
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(ANALYZER_CONFIG['MODEL_NAME']) # Use genai.GenerativeModel here
        return client
    except Exception as e:
        logging.error(f"Failed to configure or initialize Gemini client: {e}")
        raise

def analyze_app_data(client, app_data, model_name, char_limit):
    """Analyzes app data using the Gemini LLM, validates JSON output."""
    if not isinstance(app_data, dict):
        logging.error("Invalid app_data provided to analyze_app_data (must be dict).")
        return None

    if 'appId' not in app_data:
         logging.warning("App data missing 'appId' key.")

    prompt = f"""
You are a highly vigilant fraud detection expert analyzing mobile application data as of {datetime.date.today().strftime("%B %d, %Y")}. Your primary task is to assess the independent probability that the application belongs to each of the following categories: 'fraud', 'genuine', and 'suspected', based on a meticulous evaluation of objective evidence. You will also provide a concise reason for your assessment. **Your assessment of the 'fraud' probability must be particularly sensitive to *any* red flag, anomaly, or inconsistency, no matter how small.**

**Crucially, you must IGNORE hyperbolic, vague, or extreme marketing claims** found in the app's description or promotional materials. Focus *only* on verifiable facts, functional descriptions, user reviews (assessing their authenticity), permissions requested, developer history, download counts, and review volume. Do not let aspirational marketing language influence your probability assessment.

Analyze the following application data:

```json
{json.dumps(app_data, indent=2, default=str)}
Based strictly on the objective evidence within this data, provide a concise explanation and the independent probability for each category. Consider the following factors, giving appropriate weight to all potential indicators, with strong weight to major inconsistencies and red flags. Critically, ensure that the 'fraud' probability calculation reflects the cumulative weight of all identified suspicious elements, ignoring none.

Suspicious Permissions: Unnecessary permissions for stated core functionality? (Increases 'fraud')

Review Authenticity & Volume: Genuine, diverse, specific reviews? Signs of manipulation? Very low review counts or no reviews are significant red flags. (Affects all probabilities, especially 'fraud'/'suspected')

Download Count: Very low download count, inconsistent with claims/age/reviews? (Increases 'fraud'/'suspected')

Misleading Descriptions: Discrepancies, inaccuracies, exaggerations, unprofessional elements (grammar)? (Increases 'fraud')

Developer Reputation: Unknown, new, associated with suspicious apps? Lack of positive history? (Increases 'fraud'/'suspected')

Other Anomalies: Any other objective patterns, inconsistencies, lack of expected info, unusual details? (Increases 'fraud'/'suspected')

Provide your analysis in the following JSON format ONLY:

{{
"reason": "Concise explanation based on evidence ({char_limit} char max), highlighting key red flags driving the probabilities.",
"probabilities": {{
"fraud": <float_probability_0_to_1_highly_sensitive_to_red_flags>,
"genuine": <float_probability_0_to_1>,
"suspected": <float_probability_0_to_1>
}}
}}

ONLY return the JSON object. No introductory text, markdown formatting (like ```json), or explanations outside the JSON structure.

The "reason" field MUST be {char_limit} characters or less.

The "probabilities" object MUST contain exactly three keys: "fraud", "genuine", "suspected".

Each probability value MUST be a number (float) between 0.0 and 1.0.

These probabilities are independent and DO NOT need to sum to 1.0.
"""

    try:
        # Using genai.Client style to generate content
        response = client.generate_content(prompt) # CORRECT: Call directly on the client
        time.sleep(ANALYZER_CONFIG['LLM_RETRY_DELAY'])

        # JSON parsing and validation (remains the same)
        try:
            text_response = response.text
            start_index = text_response.find("{")
            end_index = text_response.rfind("}") + 1

            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("No valid JSON object boundaries found", text_response, 0)

            json_string = text_response[start_index:end_index].strip()
            result = json.loads(json_string)

            if not isinstance(result, dict):
                raise ValueError("LLM output is not a dictionary.")
            if "reason" not in result or not isinstance(result["reason"], str):
                raise ValueError("LLM output missing 'reason' string.")
            if "probabilities" not in result or not isinstance(result["probabilities"], dict):
                raise ValueError("LLM output missing 'probabilities' dictionary.")

            probs = result["probabilities"]
            required_keys = {"fraud", "genuine", "suspected"}
            if not required_keys.issubset(probs.keys()):
                raise ValueError(f"LLM 'probabilities' missing required keys. Found: {list(probs.keys())}")

            for key in required_keys:
                val = probs[key]
                if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                    try:
                        val_f = float(val)
                        if not (0.0 <= val_f <= 1.0): raise ValueError
                        probs[key] = val_f
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid probability value for '{key}': {val}")

            if len(result["reason"]) > char_limit:
                logging.warning(f"LLM reason exceeded char limit ({len(result['reason'])}>{char_limit}), truncating.")
                result["reason"] = result["reason"][:char_limit] + "..."

            return result

        except json.JSONDecodeError as e:
            logging.error(f"LLM response parsing failed. Error: {e}. Response Text: '{response.text}'")
            return None
        except ValueError as e:
            logging.error(f"LLM output validation failed: {e}. Response Text: '{response.text}'")
            return None

    except Exception as e:
        logging.error(f"Error during LLM API call: {e}")
        return None


# --- CSV Handling (rest remains the same) ---
def append_to_csv(csv_filepath, app_id, analysis_result):
    """Appends the app ID and analysis result to the CSV file."""
    file_exists = os.path.isfile(csv_filepath)
    try:
        with open(csv_filepath, 'a', newline='', encoding='utf-8') as csvfile:
            # Define fieldnames based on the expected keys from analyze_app_data + app_id
            fieldnames = ['app_id', 'reason', 'probabilities']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            if analysis_result and isinstance(analysis_result, dict):
                row_data = {
                    'app_id': app_id,
                    'reason': analysis_result.get('reason', 'Error: Reason missing'),
                    # Store probabilities as a JSON string in the CSV
                    'probabilities': json.dumps(analysis_result.get('probabilities', {}))
                }
                writer.writerow(row_data)
            else:
                # Write a row indicating failure for this app_id
                writer.writerow({
                    'app_id': app_id,
                    'reason': "Analysis Failed",
                    'probabilities': "{}"
                })
    except Exception as e:
        logging.error(f"Error writing to CSV file '{csv_filepath}': {e}")


def get_processed_app_ids(csv_filepath):
    """Reads the CSV and returns a set of app IDs already processed."""
    processed_ids = set()
    if not os.path.isfile(csv_filepath):
        return processed_ids # File doesn't exist yet

    try:
        with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
            # Handle empty file case
            try:
                reader = csv.DictReader(csvfile)
                # Ensure 'app_id' column exists
                if 'app_id' not in reader.fieldnames:
                    logging.warning(f"CSV file '{csv_filepath}' is missing 'app_id' header. Cannot check processed apps.")
                    return processed_ids # Cannot determine processed apps

                for row in reader:
                    if 'app_id' in row and row['app_id']: # Check if key exists and value is not empty
                        processed_ids.add(row['app_id'])
            except Exception as read_err: # Catch errors during reading (e.g., empty file issues)
                logging.warning(f"Could not read processed apps from '{csv_filepath}'. May re-process apps. Error: {read_err}")

    except Exception as e:
        logging.error(f"Error opening or reading CSV '{csv_filepath}': {e}")
        # Depending on desired behavior, you might want to raise an error or return empty set
    return processed_ids


# --- Main Analyzer Function (rest remains the same) ---
def load_and_analyze_apps(json_file_paths, config):
    """
    Loads app data from JSON files, analyzes using LLM, and saves to CSV.
    """
    csv_filepath = config['CSV_FILE']
    model_name = config['MODEL_NAME']
    api_key = config['API_KEY']
    char_limit = config['REASON_CHAR_LIMIT']

    try:
        client = get_gemini_client(api_key)
    except ValueError:
        return

    processed_app_ids = get_processed_app_ids(csv_filepath)
    logging.info(f"Found {len(processed_app_ids)} previously processed app IDs in '{csv_filepath}'.")

    total_files = len(json_file_paths)
    for i, json_file_path in enumerate(json_file_paths):
        logging.info(f"Processing file {i+1}/{total_files}: {json_file_path}")
        try:
            with open(json_file_path, 'rb') as f_detect:
                rawdata = f_detect.read()
                encoding_info = chardet.detect(rawdata)
                encoding = encoding_info['encoding'] if encoding_info['encoding'] else 'utf-8'

            with open(json_file_path, 'r', encoding=encoding) as f:
                data = json.load(f)

        except FileNotFoundError:
            logging.error(f"File not found: {json_file_path}. Skipping.")
            continue
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON format in file: {json_file_path}. Skipping.")
            continue
        except Exception as e:
            logging.error(f"Error reading file {json_file_path}: {e}. Skipping.")
            continue

        apps_to_process = []
        if isinstance(data, list):
            apps_to_process = data
        elif isinstance(data, dict):
            apps_to_process = [data]
        else:
            logging.error(f"Unexpected data type ({type(data)}) in {json_file_path}. Expected list or dict. Skipping.")
            continue

        apps_in_file = 0
        skipped_count = 0
        analyzed_count = 0
        failed_count = 0

        for app_data in apps_to_process:
            apps_in_file += 1
            if not isinstance(app_data, dict):
                logging.warning(f"Item in {json_file_path} is not a dictionary. Skipping item.")
                continue

            app_id = app_data.get('appId')
            if not app_id:
                logging.warning(f"App data item in {json_file_path} missing 'appId'. Skipping item: {str(app_data)[:100]}...")
                continue

            if app_id in processed_app_ids:
                skipped_count += 1
                continue

            logging.info(f"Analyzing App ID: {app_id}")
            analysis_result = analyze_app_data(client, app_data, model_name, char_limit)
            append_to_csv(csv_filepath, app_id, analysis_result)

            if analysis_result:
                analyzed_count += 1
                processed_app_ids.add(app_id)
            else:
                failed_count += 1

        logging.info(f"File {json_file_path} summary: Total items={apps_in_file}, Analyzed={analyzed_count}, Skipped (already processed)={skipped_count}, Failed analysis={failed_count}")

    logging.info(f"--- Analysis complete. Results saved to '{csv_filepath}' ---")


# --- Testing (rest remains the same) ---
if __name__ == "__main__":
    print("Running model_analyzer module directly (for testing)...")
    if not ANALYZER_CONFIG['API_KEY']:
        print("ERROR: GEMINI_API_KEY environment variable not set. Exiting.")
    else:
        test_dir = "temp_scraper_output"
        if not os.path.exists(test_dir): os.makedirs(test_dir)
        dummy_file_1 = os.path.join(test_dir, "test_cat1_details.json")
        dummy_file_2 = os.path.join(test_dir, "test_cat2_details.json")

        dummy_data_1 = [{"appId": "com.test.app1", "title": "Test App One", "description": "A genuine test app.", "score": 4.5, "reviews": 100, "installs": "1,000+"}]
        dummy_data_2 = [{"appId": "com.scam.app2", "title": "Free Money NOW!", "description": "Click here get rich quick!", "score": 1.2, "reviews": 5, "installs": "10+"}]

        try:
            with open(dummy_file_1, 'w') as f: json.dump(dummy_data_1, f)
            with open(dummy_file_2, 'w') as f: json.dump(dummy_data_2, f)

            test_json_files = [dummy_file_1, dummy_file_2]
            test_config = ANALYZER_CONFIG.copy()
            test_config['CSV_FILE'] = 'temp_analysis_results.csv'

            if os.path.exists(test_config['CSV_FILE']): os.remove(test_config['CSV_FILE'])

            load_and_analyze_apps(test_json_files, test_config)

            print(f"\nAnalysis test finished. Check '{test_config['CSV_FILE']}'.")

        except Exception as e:
            print(f"Error during testing: {e}")