import pandas as pd
import numpy as np
import re
import os
import glob
from collections import defaultdict

dict_file = "src/data/cata-dict.xlsx"

def analyze_text(transcript_path, output_speaker_dir, result_path):
    # Load transcription data and CATA dictionary
    transcript_df = pd.read_csv(transcript_path)
    dictionary_df = pd.read_excel(dict_file, sheet_name='Marks_v2')
    
    # only save the words and diction_code columns
    dictionary_df = dictionary_df[['words', 'diction_code']]
    
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
    max_time    = transcript_df['end'].max()
    
    # Create time series data structures
    time_points = np.arange(0, max_time, step_size)
    speaker_time_series = []  # Will hold (speaker, window_start, window_end, category_counts...)
    all_categories = set(category_words.keys()) | set(category_patterns.keys())
    
    for t in time_points:
        window_start = t
        window_end   = t + window_size
    
        # Filter transcript rows overlapping this window
        # Condition: utterance overlaps if start < window_end and end >= window_start
        df_window = transcript_df[
            (transcript_df['start'] < window_end) &
            (transcript_df['end']   >= window_start)
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
    for speaker in speaker_time_series_df['speaker'].unique():
        df_single = speaker_time_series_df[speaker_time_series_df['speaker'] == speaker]
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

    # Loop through each group folder for Groups 1 to 12
    for i in range(1, num_groups + 1):
        group_dir = os.path.join(base_dir, f"group {i}")
        output_group_dir = os.path.join(output_base_dir, f"group_{i}")
        
        if not os.path.exists(group_dir):
            print(f"Skipping {group_dir}, does not exist.")
            continue
        
        # Ensure output group directory exists
        os.makedirs(output_group_dir, exist_ok=True)

        # Find all transcript files ending with "_word_level_transcriptions.csv"
        transcript_files = glob.glob(os.path.join(group_dir, "*_word_level_transcriptions.csv"))

        for transcript_path in transcript_files:
            # Extract the prefix (first word before "_word_level_transcriptions")
            filename = os.path.basename(transcript_path)
            prefix = filename.split("_word_level_transcriptions")[0]

            # Define the output file path
            output_path = os.path.join(output_group_dir, f"{prefix}_group_text_analysis.csv")
            output_speaker_dir = os.path.join(output_group_dir, f"{prefix}_speaker_time_series")
            os.makedirs(output_speaker_dir, exist_ok=True)

            # Call the text analysis function
            analyze_text(transcript_path, output_speaker_dir, output_path)

    print("Processing complete!")

if __name__ == "__main__":
    main()
