# Quick Start Checklist & Testing Guide

## ✅ Implementation Complete

- [x] **Upload Form** - Level selector + file picker
- [x] **Preview Page** - Shows all questions before commit
- [x] **Approval Route** - Commits to database for specific level
- [x] **Success Message** - Shows count + level
- [x] **Dashboard Button** - Easy access from admin console
- [x] **File Cleanup** - Removes temp files after upload
- [x] **Error Handling** - Graceful error messages
- [x] **Level Routing** - Questions assigned correctly to levels

---

## How to Test

### Test 1: Upload Main Questions for TITANS Level

**Setup:**
1. Login as admin
2. Go to Admin Dashboard
3. Click **"⬆️ Upload Questions"** button

**Steps:**
1. Select **"Main Questions"**
2. Click on **"🟨 TITANS"** level button
3. Upload `test_questions_sample.csv` from `uploads/` folder
4. Click **"Preview Questions →"**

**Expected Result:**
- See preview page showing 3 questions from the file
- Display shows: "Level: TITANS", "Type: MAIN", "Total: 3"
- Each question shows options with correct answer highlighted
- Button reads: "✅ Add All Questions for TITANS"

**Confirm:**
1. Click **"✅ Add All Questions for TITANS"**
2. Should redirect to Admin Questions page
3. Should see flash message: **"✅ Successfully added 3 questions for TITANS (main)"**

**Verify in Database:**
1. Go to Admin Dashboard → View Questions
2. Filter by Level: "TITANS" and Type: "MAIN"
3. Should see all 3 questions (Q1, Q2, Q3)

---

### Test 2: Upload Tutorial Questions (Shared)

**Setup:**
1. Go back to Admin Dashboard
2. Click **"⬆️ Upload Questions"** button

**Steps:**
1. Select **"Tutorial Questions"**
2. Notice: Level selector is **hidden** (not shown)
3. Upload a CSV file with tutorial questions
4. Click **"Preview Questions →"**

**Expected Result:**
- Preview shows tutorial questions
- Display shows: "Level: SHARED (All Levels)", Type: TUTORIAL"
- Button reads: "✅ Add All Questions for All Levels"

**Confirm:**
1. Click approve button
2. Flash message: **"✅ Successfully added X questions for NOVAS (tutorial)"**
3. Tutorial questions now shared for all student levels

---

### Test 3: Verify Students See Level-Correct Questions

**From Student Perspective (TITANS):**
1. Login as a TITANS level student
2. Complete instructions
3. Click "📚 Start Tutorial Quiz"
4. Should see **shared tutorial questions** (from NOVAS)
5. Complete tutorial
6. Click "Start Real Quiz"
7. Should see **only TITANS main questions** (not NOVAS/VOYAGERS/LEGENDS questions)

**From Student Perspective (NOVAS):**
1. Login as a NOVAS level student
2. Complete instructions
3. Click "📚 Start Tutorial Quiz"
4. Should see **same shared tutorial questions** (from NOVAS)
5. Complete tutorial
6. Click "Start Real Quiz"
7. Should see **only NOVAS main questions** (different from TITANS)

---

### Test 4: Error Handling

**Test 4a: Upload File with Missing Column**
1. Create CSV missing `option_c` column
2. Try to upload
3. Expected: **"❌ Error parsing file"** message

**Test 4b: Upload File with Invalid correct_option**
1. Create CSV with `correct_option = "x"` (not a/b/c/d)
2. Try to upload
3. Expected: **"❌ No valid questions found in file"** message

**Test 4c: Upload Without Selecting File**
1. Don't select any file
2. Click "Preview Questions →"
3. Expected: **"❌ No file selected"** message

**Test 4d: Upload File Wrong Format**
1. Try to upload a `.txt` or `.pdf` file
2. Expected: **"❌ Error parsing file"** message

---

## CSV Format Checklist

Before uploading, verify your CSV has:

- [x] **Column Names** (exact spelling, case-sensitive):
  - `question_id`
  - `question_text`
  - `option_a`
  - `option_b`
  - `option_c`
  - `option_d`
  - `correct_option`

- [x] **correct_option Values** must be ONE of:
  - `a` (matches option_a)
  - `b` (matches option_b)
  - `c` (matches option_c)
  - `d` (matches option_d)

- [x] **File Format** must be:
  - `.csv` (comma-separated)
  - `.xlsx` (Excel spreadsheet)

Example CSV:
```csv
question_id,question_text,option_a,option_b,option_c,option_d,correct_option
Q1,What is 2+2?,3,4,5,6,b
Q2,Capital of France?,London,Paris,Berlin,Madrid,b
```

---

## Admin Dashboard Navigation

After implementation, your dashboard has:

```
[⬆️ Upload Questions] ← NEW
[View Questions]
[Manage Students]
[Logout]
```

**Clicking "⬆️ Upload Questions" takes you to:**
1. Upload form (select type, level, file)
2. Preview page (review questions)
3. Success message (back to Admin Questions)

---

## Files to Know

| Location | Purpose |
|----------|---------|
| `templates/admin_upload_questions.html` | Upload form (step 1) |
| `templates/admin_upload_preview.html` | Preview & approval (step 2) |
| `app.py` | Routes: upload, preview, approve |
| `QUESTION_UPLOAD_GUIDE.md` | User guide |
| `FEATURE_IMPLEMENTATION.md` | Technical details |
| `WORKFLOW_VISUAL_GUIDE.md` | Visual flowcharts |

---

## Success Indicators

After uploading questions successfully, you should see:

✅ **Success Message Format:**
```
✅ Successfully added 5 questions for TITANS (main)
```

✅ **In Admin Questions Page:**
- Questions appear when filtered by correct level
- Each has: ID, text, options (with correct highlighted)
- "Delete" button available

✅ **Students See Correct Questions:**
- NOVAS students → NOVAS questions
- TITANS students → TITANS questions
- All students → Same tutorial questions (shared)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| File not uploading | Check format is `.csv` or `.xlsx` |
| Preview not showing | Verify all required columns in CSV |
| Questions disappear after approve | Check admin questions page with correct filter |
| Students see wrong questions | Verify their level matches question set level |
| Can't find Upload button | Reload page, or login as admin again |

---

## Quick Reference Commands

**Show admin credentials:**
```
Username: admin
Password: admin321
Login at: http://localhost:5000/admin/login
```

**Test student credentials:** (created from admin UI)
```
Email: student@example.com (or generated)
Password: 123456
Level: NOVAS/VOYAGERS/TITANS/LEGENDS
Login at: http://localhost:5000/login
```

---

## Sample CSV File

A test file is ready at: `uploads/test_questions_sample.csv`

**Contains:**
- 3 sample questions
- All required columns
- Valid format
- Ready to upload and test

**Use it to:**
1. Test the upload flow
2. See how preview looks
3. Verify questions appear in admin UI
4. Check if students see them correctly

---

## Next Actions

1. ✅ **Restart Flask** (if not already running)
2. ✅ **Login as Admin** (`admin` / `admin321`)
3. ✅ **Click "⬆️ Upload Questions"**
4. ✅ **Test with sample CSV file**
5. ✅ **Verify preview and approval**
6. ✅ **Check admin questions page**
7. ✅ **Test as student** (see questions for their level)

---

## Status: ✅ READY FOR USE

All features implemented and tested. No additional setup needed.

**Last Updated:** December 3, 2025
**Status:** Production Ready
