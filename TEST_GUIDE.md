# Quick Test Guide - Admin Features

## 🧪 How to Test the New Features

### Prerequisites
- Flask app running on http://localhost:5000
- Admin logged in
- 25 questions per level imported (100+ total questions in database)

---

## Test 1: View All Submissions

**Steps:**
1. Login as admin (credentials: admin / admin)
2. Navigate to **Dashboard** → Click "📊 Quiz Submissions" button
3. Or go directly to: `http://localhost:5000/admin/submissions`

**Expected Result:**
- Table showing all student quiz submissions
- Columns: Email, Name, Level, Score, Percentage, Status, Completed Date, Violations
- Each row has "View Details" and "Download Certificate" buttons
- Status shows "PASS" (green) for ≥60% or "FAIL" (red) for <60%

**If No Submissions:**
- Message displays: "No submissions yet. Students haven't completed the quiz."

---

## Test 2: View Submission Details

**Steps:**
1. From submissions page, click **"View Details"** button for any submission
2. Or go to: `http://localhost:5000/admin/submission/[submission_id]`

**Expected Result:**
- Student info displayed: Name, Email, Level, Completion Date
- Score summary: e.g., "15/25 (60.0%)" with PASS/FAIL badge
- Table with answer breakdown:
  - Q1, Q2, Q3, etc. (question numbers)
  - Question text
  - Student's answer (with option letter)
  - Correct answer (with option letter)
  - Result badge (✓ Correct or ✗ Wrong)
- "Download Certificate" button at top

---

## Test 3: Download Certificate

**Steps:**
1. From submission details page, click **"⬇️ Download Certificate"** button
2. Or from submissions page, click **"Download Certificate"** button for any row
3. Or go to: `http://localhost:5000/admin/certificate/[submission_id]`

**Expected Result:**
- PDF file downloads with filename: `Certificate_[StudentName]_[SubmissionID].pdf`
- Certificate opens showing:
  - Professional blue header and border
  - "Certificate of Completion" or similar title
  - Student Name
  - Score: X/Y (e.g., "15/25")
  - Percentage: XX% (e.g., "60%")
  - Level: NOVAS / VOYAGERS / TITANS / LEGENDS
  - Completion Date
  - Certificate ID
  - Professional styling with blue accents

---

## Test 4: Verify Questions Imported

**Steps:**
1. Login as student (e.g., `daman@questx.com` / password: `daman`)
2. Complete tutorial (skip if desired)
3. Start quiz by clicking "Start Quiz"
4. Observe the questions shown

**Expected Results by Level:**
- **NOVAS** (usama@questx.com): Should see ~25 basic math/logic questions
- **VOYAGERS** (daman@questx.com): Should see ~25 intermediate questions
- **TITANS** (zaman@questx.com): Should see ~25 advanced questions
- **LEGENDS** (vajiya@questx.com): Should see ~25 expert/physics questions

**Each question should have:**
- Question number (1-25)
- Question text
- 4 multiple choice options
- Image placeholder (white background if no image)

---

## Test 5: Complete Student Quiz & Track in Admin

**Steps:**
1. Login as any test student
2. Follow: Instructions → Tutorial → Quiz
3. Answer some/all questions
4. Click "Submit Quiz" button
5. Login as admin
6. Go to **Submissions** page

**Expected Result:**
- New submission appears in submissions table
- Shows student email, name, level, score, percentage
- Can click "View Details" to see which questions were right/wrong
- Can download certificate with student's name and score

---

## Troubleshooting

### "No Submissions" showing but students have completed quizzes
- **Cause**: Submissions table is empty or credentials not marked as 'used'
- **Fix**: Check database with: `SELECT COUNT(*) FROM submissions`

### Certificate PDF doesn't download
- **Cause**: Missing submission ID
- **Fix**: Verify submission exists in database: `SELECT id FROM submissions`

### Questions not showing in quiz
- **Cause**: Questions not imported or test_id mismatch
- **Fix**: 
  1. Check database: `SELECT COUNT(*) FROM questions`
  2. If <100 questions, run import again via admin dashboard

### Import button not working
- **Cause**: CSV files not found or admin not logged in
- **Fix**:
  1. Verify CSV files exist: Check `uploads/` folder for NOVAS/VOYAGERS/TITANS/LEGENDS CSVs
  2. Ensure logged in as admin
  3. Check browser console for errors

---

## Sample Test Data

**Test Students:**
- usama@questx.com (NOVAS - Level 1)
- daman@questx.com (VOYAGERS - Level 2)
- zaman@questx.com (TITANS - Level 3)
- vajiya@questx.com (LEGENDS - Level 4)
- test1@questx.com (NOVAS - Level 1)

**Admin Credentials:**
- Username: admin
- Password: admin

---

## Database Verification Commands

To verify data in SQLite:

```sql
-- Check total questions
SELECT COUNT(*) FROM questions;

-- Check questions per level
SELECT t.level, COUNT(q.id) 
FROM tests t 
LEFT JOIN question_sets qs ON qs.test_id = t.id AND qs.set_type='main'
LEFT JOIN questions q ON q.set_id = qs.id
GROUP BY t.level;

-- Check submissions
SELECT r.email, r.name, s.score, s.total_points, c.level 
FROM submissions s 
JOIN respondents r ON s.respondent_id = r.id 
LEFT JOIN student_credentials c ON r.email = c.email 
ORDER BY s.finished_at DESC;
```

---

## Feature Checklist

- [ ] Admin Submissions page displays all submissions
- [ ] Status badges show PASS/FAIL correctly
- [ ] View Details button shows answer breakdown
- [ ] Questions with correct/wrong marks display correctly
- [ ] Download Certificate button generates PDF
- [ ] Certificate shows student name, score, level, date
- [ ] Students see appropriate level questions in quiz
- [ ] Student answers are recorded with details
- [ ] Percentage calculations are correct (score/total * 100)

---

**Last Updated:** 2025-12-04

All features implemented and ready for testing!
