import pandas as pd
import json
import logging
import os

# Setup logging for evaluator
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions (Keep these as they are) ---
def parse_probabilities(json_str):
    """ Safely parse JSON string from the probabilities column. """
    if pd.isna(json_str):
        return None
    try:
        if isinstance(json_str, str) and json_str.startswith('"') and json_str.endswith('"'):
             json_str = json.loads(json_str)
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logging.warning(f"Could not parse probabilities JSON: {json_str}. Error: {e}")
        return None

def classify_probability(row, fraud_threshold=0.7, genuine_threshold=0.7, suspect_threshold=0.4):
    """ Classifies an app based on probability scores using prioritized logic. """
    fraud_prob = row.get('fraud')
    genuine_prob = row.get('genuine')
    suspected_prob = row.get('suspected')
    f_p = fraud_prob if pd.notna(fraud_prob) else 0.0
    g_p = genuine_prob if pd.notna(genuine_prob) else 0.0
    s_p = suspected_prob if pd.notna(suspected_prob) else 0.0
    if f_p >= fraud_threshold: return 'fraud'
    if f_p > 0.1 and g_p < 0.5 and f_p >= g_p * 1.5: return 'fraud'
    if g_p >= genuine_threshold and g_p >= s_p : return 'genuine'
    if s_p >= suspect_threshold and s_p >= g_p: return 'suspected'
    if g_p > 0.5 and g_p > s_p: return 'genuine'
    if s_p > 0.1: return 'suspected'
    return 'suspected'

# --- Modified Evaluation Function ---
def evaluate_results(csv_filepath, **kwargs):
    """
    Loads analysis CSV, processes data, adds numerical 'type', selects final columns,
    and **overwrites the original CSV file** with the result ('app_id', 'reason', 'type').

    Args:
        csv_filepath (str): Path to the CSV file to read from and write back to.
        **kwargs: Additional arguments to pass to classify_probability.

    Returns:
        pd.DataFrame or None: The processed DataFrame that was saved,
                              or None if reading/processing failed.
    """
    logging.info(f"Starting evaluation process for: {csv_filepath}")
    try:
        df = pd.read_csv(csv_filepath)
        logging.info(f"Loaded {len(df)} rows from CSV.")
    except FileNotFoundError:
        logging.error(f"Evaluation failed: CSV file not found at {csv_filepath}")
        return None
    except Exception as e:
        logging.error(f"Evaluation failed: Error reading CSV {csv_filepath}: {e}")
        return None

    required_input_cols = ['app_id', 'reason', 'probabilities']
    if not all(col in df.columns for col in required_input_cols):
        missing_cols = [col for col in required_input_cols if col not in df.columns]
        logging.error(f"Evaluation failed: Input CSV missing required columns: {missing_cols}")
        return df

    # --- Perform Processing (Steps 1-4 from previous version) ---
    df['parsed_probs'] = df['probabilities'].apply(parse_probabilities)
    df_valid = df.dropna(subset=['parsed_probs']).copy()
    if len(df_valid) < len(df):
         logging.warning(f"Dropped {len(df) - len(df_valid)} rows due to invalid or missing probability JSON.")

    # Handle case where no rows are valid after parsing probabilities
    if df_valid.empty:
        logging.warning("No valid probability data found. Overwriting CSV with headers only.")
        df_output = pd.DataFrame(columns=['app_id', 'reason', 'type']) # Prepare empty DF with correct columns
    else:
        df_valid['fraud'] = df_valid['parsed_probs'].apply(lambda x: x.get('fraud') if isinstance(x, dict) else None)
        df_valid['genuine'] = df_valid['parsed_probs'].apply(lambda x: x.get('genuine') if isinstance(x, dict) else None)
        df_valid['suspected'] = df_valid['parsed_probs'].apply(lambda x: x.get('suspected') if isinstance(x, dict) else None)
        df_valid['fraud'] = pd.to_numeric(df_valid['fraud'], errors='coerce')
        df_valid['genuine'] = pd.to_numeric(df_valid['genuine'], errors='coerce')
        df_valid['suspected'] = pd.to_numeric(df_valid['suspected'], errors='coerce')
        logging.info("Applying classification logic...")
        df_valid['predicted_class'] = df_valid.apply(lambda row: classify_probability(row, **kwargs), axis=1)
        label_to_type_map = {'fraud': 0, 'genuine': 1, 'suspected': 2, 'undetermined': -1}
        df_valid['type'] = df_valid['predicted_class'].map(label_to_type_map)
        df_valid['type'] = df_valid['type'].astype('Int64')

        # Select final columns
        final_columns = ['app_id', 'reason', 'type']
        if not all(col in df_valid.columns for col in final_columns):
             logging.error(f"Internal error: Could not create all required output columns {final_columns}.")
             return None # Don't save if columns are missing
        df_output = df_valid[final_columns].copy()
    # --- End Processing ---


    # --- NEW: Save the processed DataFrame back to the original file ---
    try:
        logging.info(f"Attempting to save processed data back to: {csv_filepath}")
        df_output.to_csv(csv_filepath, index=False, encoding='utf-8') # index=False is important!
        logging.info(f"Successfully overwrote '{csv_filepath}' with processed data ({len(df_output)} rows).")
    except Exception as e:
        logging.error(f"Failed to save processed data back to '{csv_filepath}': {e}")
        return None # Return None if saving failed
    # --- END NEW ---

    # Log final distributions from the saved data
    logging.info("Evaluation complete (file overwritten).")
    if not df_output.empty:
        logging.info("Saved Type distribution ('type'):\n" + str(df_output['type'].value_counts()))

    return df_output # Return the DataFrame that was saved

# --- Example Testing Code ---
if __name__ == "__main__":
    print("Running evaluator module directly (for testing)...")
    # Use a specific temporary file for this test to avoid damaging real data
    test_csv = 'temp_evaluator_overwrite_test.csv'
    dummy_data = {
        'app_id': ['com.test.app1', 'com.scam.app2', 'com.maybe.app3', 'com.legit.app4', 'com.broken.app5', 'com.zero.app6'],
        'reason': ['Looks good', 'Obvious scam', 'Some red flags', 'Very genuine', 'Analysis Failed', 'All zero probs'],
        'probabilities': [ # This column will be removed in the output file
            '{"fraud": 0.05, "genuine": 0.9, "suspected": 0.1}',
            '{"fraud": 0.95, "genuine": 0.01, "suspected": 0.8}',
            '{"fraud": 0.4, "genuine": 0.5, "suspected": 0.6}',
            '{"fraud": 0.01, "genuine": 0.98, "suspected": 0.05}',
            '{}', # Invalid JSON -> will be dropped
            '{"fraud": 0.0, "genuine": 0.0, "suspected": 0.0}', # Undetermined
        ],
        'extra_col': [1,2,3,4,5,6] # This column should also be removed
    }
    try:
        # 1. Create the initial test file
        pd.DataFrame(dummy_data).to_csv(test_csv, index=False)
        print(f"Created initial test file: {test_csv}")
        print("Initial file content sample:")
        print(pd.read_csv(test_csv).head())

        # 2. Run evaluation (which will overwrite the file)
        processed_df = evaluate_results(test_csv, fraud_threshold=0.7, genuine_threshold=0.7, suspect_threshold=0.4)

        if processed_df is not None:
            print("\nFunction returned processed DataFrame sample:")
            print(processed_df.head()) # Show what the function returned

            # 3. Verify the content of the overwritten file
            print(f"\nVerifying content of overwritten file: {test_csv}")
            final_df_read = pd.read_csv(test_csv)
            print("Final file content sample:")
            print(final_df_read.head())
            print("\nFinal file columns:", final_df_read.columns.tolist())
            if final_df_read.columns.tolist() == ['app_id', 'reason', 'type']:
                print("File overwrite successful: Columns match expected output.")
            else:
                print("File overwrite WARNING: Columns DO NOT match expected output.")

        else:
            print("Evaluation returned None (likely file error or no valid data). File may not have been overwritten.")

    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        # Clean up the test file
        if os.path.exists(test_csv):
             os.remove(test_csv)
             print(f"\nCleaned up test file: {test_csv}")