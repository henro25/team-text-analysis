import pandas as pd
import numpy as np
import re
import os
import glob
import json
from collections import defaultdict

dict_file = "src/data/cata-dict.xlsx"
json_file_path = "src/data/task_cutoffs.json"

def analyze_text(transcript_path, output_speaker_dir, result_path, task_cutoff):
    # Load transcription data and CATA dictionary
    transcript_df = pd.read_csv(transcript_path)
    dictionary_df = pd.read_excel(dict_file, sheet_name='Marks_v2')
    
    # only save the words and diction_code columns
    dictionary_df = dictionary_df[['words', 'diction_code']]
    
    # Convert 'start' and 'end' columns to numeric, forcing non-numeric values to NaN
    transcript_df['start'] = pd.to_numeric(transcript_df['start'], errors='coerce')
    transcript_df['end'] = pd.to_numeric(transcript_df['end'], errors='coerce')

    # Drop rows where conversion failed (if any)
    transcript_df.dropna(subset=['start', 'end'], inplace=True)
    
    # Only keep rows between start and end cutoff times
    transcript_df = transcript_df[
        (transcript_df['start'] >= task_cutoff['start']) & (transcript_df['end'] <= task_cutoff['end'])]
    
    # Extract category-wise words, handling wildcards and context-based words
    category_words = defaultdict(set)  # Stores direct words (key: category, value: set of words)
    category_patterns = defaultdict(list)  # Stores regex patterns and context-based words

    for _, row in dictionary_df.iterrows():
        word = str(row['words']).strip().lower()  # Normalize word
        category = row['diction_code']
        
        # Skip negative diction codes
        if category[0]== 'N':
            continue

        # Handle wildcard "*"
        if '*' in word:
            regex_pattern = re.sub(r'\*', r'.*', word)  # Convert * to regex pattern
            category_patterns[category].append(re.compile(regex_pattern))
        else:
            category_words[category].add(word)  # Store as a normal word
            
    # Preprocess transcript
    transcript_df = transcript_df[['start', 'end', 'text', 'speaker']].dropna()
    transcript_df['text'] = transcript_df['text'].str.lower().apply(lambda x: re.findall(r'\b\w+\b', x))
    
    # Define window params
    window_size = 30    # 30-second window
    step_size   = 15    # 15-second overlap step

    # Participant devices
    participant_speakers = ["HCILab1", "HCILab2", "CSL_Laptop", "CSL_LabPC"]
    
    # Create time series data structures
    time_points = np.arange(task_cutoff['start'], task_cutoff['end'], step_size)
    speaker_time_series = []  # Will hold (speaker, window_start, window_end, category_counts...)
    all_categories = set(category_words.keys()) | set(category_patterns.keys())
    
    for t in time_points:
        window_start = t
        window_end   = t + window_size
    
        # Filter transcript rows overlapping this window
        # Condition: utterance overlaps if start < window_end and end >= window_start
        df_window = transcript_df[
            transcript_df['speaker'].isin(participant_speakers) &
            (transcript_df['end'] < window_end) &
            (transcript_df['end'] >= window_start)
            ]
        
        # We'll keep track of counts for each speaker → each category
        # e.g., speaker_category[speaker][category] = count
        speaker_category = defaultdict(lambda: defaultdict(int))
        
        # For each row, tokenize and match words
        for _, row in df_window.iterrows():
            speaker = row['speaker']
            
            # Tokenize text (lowercase, alphanumeric)
            tokens = re.findall(r'\b\w+\b', str(row['text']).lower())
            
            # Match direct words
            for cat, words_set in category_words.items():
                for token in tokens:
                    if token in words_set:
                        speaker_category[speaker][cat] += 1
            
            # Match wildcard/regex patterns
            for cat, pattern_list in category_patterns.items():
                for pat in pattern_list:
                    for token in tokens:
                        if pat.match(token):
                            speaker_category[speaker][cat] += 1
        
        # Make an empty row if there are no speakers for this window
        if len(df_window) == 0:
            _ = speaker_category["None"]
        
        # For each speaker we found in the current window, create a row
        # that includes category counts for all categories.
        # If a speaker has zero for a category, it won't appear in speaker_category,
        # so we must fill in 0 for missing categories.
        for speaker, cat_counts in speaker_category.items():
            row_dict = {
                'speaker': speaker,
                'window_start': window_start,
                'window_end':   window_end
            }
            # Make sure all categories appear
            for cat in all_categories:
                row_dict[cat] = cat_counts.get(cat, 0)

            speaker_time_series.append(row_dict)
        
    # Convert to DataFrame
    speaker_time_series_df = pd.DataFrame(speaker_time_series)
    speaker_time_series_df.sort_values(by=['window_start','speaker'], inplace=True)
    
    # Output each individual speaker's time series as a separate CSV file
        for speaker in speaker_time_series_df[speaker_time_series_df['speaker'] != 'None']['speaker'].unique():
        df_single = speaker_time_series_df[speaker_time_series_df['speaker'].isin([speaker, 'None'])]

        missing_rows = speaker_time_series_df[~speaker_time_series_df['window_start'].isin(
            df_single['window_start'])].groupby(['window_start', 'window_end']).agg(
            {'speaker': (lambda x: "None"), **{col: (lambda x: 0) for col in speaker_time_series_df.columns if
             col not in ['window_start', 'window_end', 'speaker']}}
        )

        df_single = pd.concat([df_single, missing_rows], ignore_index=True).sort_values(by=[
            'window_start']).reset_index(drop=True)
        
        # Build a filename for this speaker
        output_filename = f"{output_speaker_dir}/{speaker}_time_series.csv"
        df_single.to_csv(output_filename, index=False)
        print(f"Saved {output_filename}")
    
    # We can group by (window_start, window_end) and sum across speakers
    speaker_agg = lambda x: ', '.join(sorted(x.unique()))

    group_time_series_df = speaker_time_series_df.groupby(['window_start', 'window_end']).agg(
        {**{col: 'sum' for col in speaker_time_series_df.columns if col not in ['window_start', 'window_end', 'speaker']},
        'speaker': speaker_agg}
    ).reset_index()

    group_time_series_df.to_csv(result_path, index=False)
    print(f"Analyzing {transcript_path} -> Saving results to {result_path}")

def main():
    # Change working directory to the root directory of the script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))  # Moves up one level
    os.chdir(root_dir)
    
    print("Starting text analysis...")
    base_dir = "src/data/transcripts"
    output_base_dir = "src/data/analysis_results"
    num_groups = 12
    
    # Ensure output directories exist
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Open and load the task cutoff times JSON file
    with open(json_file_path, 'r') as f:
        task_cutoffs = json.load(f)

    # Loop through each group folder for Groups 1 to 12
    for i in range(1, num_groups + 1):
        output_group_dir = os.path.join(output_base_dir, f"group_{i}")

        # Find the corresponding group transcript file ending with "_word_level.csv"
        transcript_files = glob.glob(os.path.join(base_dir, f"group{i}_word_level.csv"))

        if transcript_files:
            # Extract the prefix (first word before "_word_level")
            transcript_path = transcript_files[0]
            filename = os.path.basename(transcript_path)
            prefix = filename.split("_word_level")[0]

            # Define the output file path
            os.makedirs(output_group_dir, exist_ok=True)
            output_path = os.path.join(output_group_dir, f"{prefix}_group_text_analysis.csv")
            output_speaker_dir = os.path.join(output_group_dir, f"{prefix}_speaker_time_series")
            os.makedirs(output_speaker_dir, exist_ok=True)

            # Call the text analysis function
            analyze_text(transcript_path, output_speaker_dir, output_path, task_cutoffs[f"group {i}"])

    print("Processing complete!")

if __name__ == "__main__":
    main()
