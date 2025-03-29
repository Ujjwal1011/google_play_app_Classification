# Google Play App Analysis Workflow

## Overview

This project automates the process of scraping mobile app data from the Google Play Store, analyzing it using a Large Language Model (LLM), and evaluating the analysis results to detect potentially fraudulent applications. It leverages the `google_play_scraper` library for data scraping, the Gemini API for LLM-based analysis, and various data science tools for evaluation and reporting.

## Key Features

*   **Automated Scraping:** Scrapes app data (title, description, reviews, etc.) from the Google Play Store.
*   **LLM-Based Analysis:** Uses the Gemini API to analyze app descriptions and identify potentially fraudulent characteristics.
*   **Fraud Detection:** Classifies apps as fraud, genuine, or suspected based on the LLM analysis and probability scores.
*   **Performance Evaluation:** Provides metrics such as accuracy, confusion matrix, and classification report to evaluate the workflow's performance.
*   **Proxy Support:** Supports the use of proxies to prevent IP blocking during scraping.

## Project Files

*   **combined.py:** Combines the scraper, analyzer, and evaluator into a single workflow. Provides functions to run the full workflow or analyze existing JSON files.
*   **evaluator.py:** Contains functions for evaluating the LLM's analysis results, classifying apps, and generating performance metrics.
*   **main.ipynb:** A Jupyter Notebook demonstrating how to use the workflow, including examples of scraping, analyzing pre-existing data, and evaluating results.
*   **model_analyzer.py:** Implements the LLM-based analysis of app data using the Gemini API.
*   **scraper.py:** Contains functions for scraping app data from the Google Play Store.
*   **good_proxies.txt:** A placeholder file for a list of proxy IPs and ports to be used for scraping.
*   **app_analysis_results.csv:** Default output file for storing the LLM analysis results in CSV format.
*   **temp_analysis_results.csv:** Temporary CSV file used for testing the `model_analyzer` module.
*   **temp_evaluator_overwrite_test.csv:** Temporary CSV file used for testing the `evaluator` module's overwrite functionality.
*   **temp_scraper_output/:** Directory where scraped app data JSON files are stored during testing.
*   **test data/:** Contains sample JSON files (`fraud-apps.json`, `genuine-apps.json`) used for testing.
*   **test_analysis_results.csv:** CSV file containing analysis results for the sample test data, used for evaluation testing in `main.ipynb`.
*   **Documentation.md:** Documentation in markdown format.
*   **Documentation.html:** Documentation in html format.

## Setup Instructions

1.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    *(Make sure you have a `requirements.txt` file listing dependencies like `google-play-scraper`, `pandas`, `google-generativeai`, `python-dotenv`, `chardet`, `scikit-learn`, `matplotlib`, `seaborn`)*

2.  **Configure API Key:**

    *   Set the `GEMINI_API_KEY` environment variable with your Google Gemini API key. You can obtain one from [Google AI Studio](https://makersuite.google.com/).

3.  **Proxy Setup (Optional but Recommended):**

    *   Populate `good_proxies.txt` with a list of working proxies (IP:Port format, one per line) to avoid IP blocking during scraping. If you don't have proxies, the scraper will attempt to run directly, but may be less reliable and could lead to IP blocking.


## Results

This project automates the process of scraping mobile app data from the Google Play Store, analyzing it using a Large Language Model (LLM), and evaluating the analysis results to detect potentially fraudulent applications.


**Key Metrics:**

*   **Accuracy**: 92.00%

*   **Confusion Matrix**:

    ![Confusion Matrix](Test_confusion_matrix.png)


*   **Classification Report**:

    ```
              precision    recall  f1-score  support
    0           0.89        0.98      0.93    50.00
    1            1.0        0.86      0.92    50.00
    2                0         0         0     0.00
    accuracy                          0.92   100.00
    weighted avg 0.94       0.92      0.92   100.00
    ```




## Usage

1.  **Scraping:** Use the functions in `scraper.py` or the combined workflow in `combined.py` to scrape app data from the Google Play Store.
2.  **Analysis:** Use the functions in `model_analyzer.py` or `combined.py` to analyze the scraped app data using the Gemini API.
3.  **Evaluation:** Use the functions in `evaluator.py` or the `main.ipynb` notebook to evaluate the analysis results and generate performance metrics.

## Notes

*   Ensure you have a valid Google Gemini API key and that it is correctly set as an environment variable.
*   Using proxies is highly recommended for scraping to prevent IP blocking. Regularly update your proxy list in `good_proxies.txt`.
*   The LLM analysis quality depends on the prompt in `model_analyzer.py` and the capabilities of the Gemini model. Prompt engineering and model selection can impact results.
*   The evaluation metrics provide insights into the workflow's classification accuracy, but further analysis and fine-tuning may be needed for specific use cases.

## Future Work

*   **Prompt Engineering:** Further experimentation and refinement of the prompts used in `model_analyzer.py` to improve the accuracy and reliability of the LLM-based analysis. This includes exploring different prompt structures, adding more context, and testing various prompt engineering techniques.
*   **Review Analysis:** Implement analysis of app reviews in addition to app descriptions to improve fraud detection accuracy. This could involve sentiment analysis, topic modeling, and identifying patterns in user feedback.
*   **Data Transfer Techniques:** Explore alternative data transfer methods between Python files instead of relying on CSV files. This could include using in-memory data structures or more efficient serialization formats.
*   **Proxy Management:** Enhance the scraper to automatically remove bad proxies and add new proxies to the `good_proxies.txt` file.
*   **Scraping Improvements:** Reduce sleep time during scraping and increase the number of apps scraped per search query to improve efficiency.
*   **Derived Attributes:** Create new derived attributes in `model_analyzer.py` based on the scraped data to provide additional features for the LLM to analyze. These attributes could be combinations of existing data or new metrics calculated from the scraped information.
