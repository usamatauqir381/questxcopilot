# Question Upload with Level Selection & Approval

## Overview
Admins can now upload question files (CSV/XLSX) with a two-step preview-and-approve workflow. Questions are assigned to a specific level and only show to students of that level.

## Feature Flow

### Step 1: Access Upload Page
- Go to **Admin Dashboard** → Click **⬆️ Upload Questions** button
- Choose question type:
  - **Main Questions** (graded, level-specific)
  - **Tutorial Questions** (practice, shared across all levels)

### Step 2: Select Level & Upload File
For **Main Questions**:
- Select one level: **NOVAS**, **VOYAGERS**, **TITANS**, or **LEGENDS**
- All questions in the file will be added to that level only

For **Tutorial Questions**:
- Level selector is hidden (auto-set to NOVAS, shared across all levels)

### Step 3: File Format & Upload
Upload a **CSV** or **XLSX** file with these required columns:
```
question_id    | question_text      | option_a | option_b | option_c | option_d | correct_option | image_url (optional)
---
Q1             | What is 2+2?       | 3        | 4        | 5        | 6        | b              | 
Q2             | Capital of France? | London   | Paris    | Berlin   | Madrid   | b              | 
```

**Important:** `correct_option` must be one of: `a`, `b`, `c`, or `d`

### Step 4: Preview Questions
- File is parsed and validated
- All questions from the file are displayed in a preview card:
  - Question ID and text
  - All four options (correct option highlighted in green)
  - File name, type, level, and total count shown at top

### Step 5: Approve & Commit
- Review preview to ensure all questions are correct
- Click **✅ Add All Questions for [LEVEL]** button
- Questions are committed to the database for that level
- Success message shows: "✅ Successfully added X questions for [LEVEL] (main)"

### Step 6: View in Admin UI
- Go to **Admin Dashboard** → **View Questions**
- Filter by level and type to see the newly added questions

## Student Experience
- Students only see questions for their assigned level
- Tutorial questions (shared NOVAS tutorial) appear to all students during the practice phase
- Main questions show after tutorial is complete (level-specific only)

## CSV Format Example

```csv
question_id,question_text,option_a,option_b,option_c,option_d,correct_option
Q1,What is the capital of France?,London,Paris,Berlin,Madrid,b
Q2,Which number is prime?,4,6,7,8,c
Q3,What is 10 divided by 2?,3,4,5,6,b
```

## XLSX Format
Same columns as CSV, save as `.xlsx` file

## API Endpoints (for reference)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/upload-questions` | GET | Show upload form |
| `/admin/upload-questions-preview` | POST | Parse file and show preview |
| `/admin/approve-questions` | POST | Commit questions to DB |

## Error Handling
- **No file selected**: Error message shown
- **Invalid file format**: Error with details
- **No valid questions in file**: Error message guides correct format
- **Missing columns**: File parsing error shown with expected columns

## Temporary Files
- Uploaded files are stored temporarily in `uploads/` during preview
- Automatically deleted after approval or cancellation

## Success Messages
After approval, you'll see:
```
✅ Successfully added 5 questions for TITANS (main)
```

This tells you:
- Number of questions added
- Level they were assigned to
- Type (main or tutorial)

## Notes
- Questions are added to the database immediately upon approval
- No rollback available; review carefully in preview before approving
- Duplicate `question_id` values will be inserted separately (allowed)
- Tutorial questions are always shared (set to NOVAS test, visible to all levels)
