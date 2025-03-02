# team-text-analysis
A team communication analysis tool using [CATA (Computer-Aided Text Analysis)](https://uchuskypack.com/surveys-tools/) for processing transcribed speech data for a WPI EEG Research Study.

## Repo Structure

```plaintext
team-text-analysis/
├── src/
│   ├── data/
│   │   ├── analysis_results/      # Output folder for processed results
│   │   ├── transcripts/           # Raw transcripts (group-wise)
│   │   ├── cata-dict.xlsx         # CATA dictionary for word classification
│   │   └── CATA.pdf               # Research paper describing the CATA framework
│   ├── analyze_text.py            # Main script for analyzing transcripts
│   └── analyze_text_test.ipynb    # Jupyter notebook for testing analysis
├── venv/                          # Virtual environment (optional)
├── .gitignore                     # Ignore unnecessary files
├── requirements.txt               # Required dependencies
└── README.md                      # Project documentation
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/henro25/team-text-analysis.git
cd team-text-analysis
```
2. Create and activate a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate     # On Windows
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```

##  Usage

Run the main script to process all transcript files in `src/data/transcripts/group_i`:
```bash
python src/analyze_text.py
```

This script:

1. Iterates through `src/data/transcripts/group_i/` (i = 1 to 12)
2. Processes all `*_word_level_transcriptions.csv` files
3. Saves results in `src/data/analysis_results/group_i/` as `{prefix}_group_text_analysis.csv`
