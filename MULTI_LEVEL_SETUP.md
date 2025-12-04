# Multi-Level Quiz Setup Guide

## Overview
Your test portal now supports **4 distinct quiz levels** for different year groups:
- **NOVAS** - Smart Quest Year 3-4 (Beginner)
- **VOYAGERS** - Smart Quest Year 5-6 (Intermediate)  
- **TITANS** - Master Quest Year 7-8 (Advanced)
- **LEGENDS** - Master Quest Year 9-10 (Master)

Each level has its own:
- Separate test instance in the database
- Question bank
- Quiz session tracking
- Student credentials assigned to a specific level

## How It Works

### 1. Database Structure
- **student_credentials** table now has a `level` column (defaults to NOVAS)
- **tests** table now tracks `level` along with `slug`
- Composite unique constraint: (slug, level) — allows same slug for all 4 levels

### 2. Student Level Assignment
When you import students, assign them to a level using the format:

```
email@domain.com,LEVEL_NAME
```

**Example import data:**
```
john@school.com,NOVAS
jane@school.com,VOYAGERS
mike@school.com,TITANS
sarah@school.com,LEGENDS
```

If no level is provided, defaults to **NOVAS**.

### 3. Login Flow
1. Student enters email, password, and name
2. System validates credentials and **retrieves their assigned level**
3. System fetches the **quiz row for that level** (e.g., test ID 2 for VOYAGERS)
4. Student is locked into their level's quiz for the entire session

### 4. Admin Features

#### Import Students with Levels
1. Go to **Admin Dashboard** → **Import Credentials** (or **Manage Credentials** → **Import**) 
2. Paste data in format: `email@domain.com,LEVEL_NAME`
3. Valid levels: NOVAS, VOYAGERS, TITANS, LEGENDS
4. Password defaults to `123456` for all imports

#### View Student Levels
1. Go to **Admin Dashboard** → **Manage Credentials**
2. Table now shows each student's assigned level (displayed as a badge)
3. Sort/filter by level to see which students are in each group

#### Per-Level Question Banks
Each level has its own question set:
- Upload different question files for each level
- Questions are tagged with the test_id for that level
- When a student starts the quiz, they see questions for their level only

## File Modifications

### Backend (app.py)
- `student_credentials` schema: added `level` column
- `tests` schema: added `level` column, changed unique constraint to (slug, level)
- `init_db()`: creates 4 test rows (one per level) on startup
- `login_post()`: retrieves student level and validates test for that level
- `admin_import_post()`: parses `email,level` format
- `instructions()`: passes level info to template

### Templates
- **admin_import.html**: updated instructions to show `email,level` format
- **admin_credentials.html**: displays level column in credentials table
- **instructions.html**: displays level badge (e.g., "Smart Quest - Year 3-4")

## Quick Start

### Step 1: Import Students with Levels
```
Example data to paste in import form:

student1@school.com,NOVAS
student2@school.com,NOVAS
student3@school.com,VOYAGERS
student4@school.com,TITANS
student5@school.com,LEGENDS
```

### Step 2: Upload Question Banks (One per Level)
1. Admin Dashboard → Upload Questions (or Quiz Control)
2. Upload a CSV with questions for each level separately
3. Each upload associates with a specific test_id (level)

### Step 3: Distribute Links
Give students access with links:
- Base: `http://your-domain/` 
- (Level is determined by their login credentials, not the URL)

### Step 4: Monitor Progress
- **Results Dashboard**: Shows submissions grouped by level
- **Student Credentials**: Filter by level to see who's in each group
- Each submission is tagged with the student's level

## Troubleshooting

**Q: What if a student logs in but no quiz appears?**
- Check that a test row exists for their level (`SELECT * FROM tests WHERE level='THEIR_LEVEL'`)
- Verify questions are uploaded for that level's test_id

**Q: Can I change a student's level after they're imported?**
- Currently: No automatic UI for this. Contact admin to modify the database directly:
  ```sql
  UPDATE student_credentials SET level='LEGENDS' WHERE email='student@domain.com'
  ```

**Q: Can multiple question sets be assigned to one level?**
- Yes. Import multiple question files for the same level — they're all associated with that level's test_id.

**Q: How do I see which level a student belongs to?**
- Admin Credentials page shows the level badge for each student
- Or query: `SELECT email, level FROM student_credentials`

## Database Queries

View all levels and their test IDs:
```sql
SELECT id, slug, level, name FROM tests;
```

View students by level:
```sql
SELECT email, level, status FROM student_credentials WHERE level='VOYAGERS';
```

View questions for a specific level:
```sql
SELECT q.id, q.text FROM questions q
JOIN question_sets qs ON q.set_id = qs.id
WHERE qs.test_id = (SELECT id FROM tests WHERE level='TITANS');
```

View submissions by level:
```sql
SELECT s.id, r.email, r.name, s.score, s.total_points
FROM submissions s
JOIN respondents r ON s.respondent_id = r.id
WHERE s.test_id IN (SELECT id FROM tests WHERE level='NOVAS');
```
