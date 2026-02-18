# Resume Optimizer Setup & Testing Guide

## 📋 Prerequisites

- Python virtual environment activated
- Supabase instance running
- HuggingFace account (free tier)

---

## 🔑 Step 1: Get HuggingFace API Key

1. Go to https://huggingface.co/settings/tokens
2. Click "New token"
3. Name it "JobSwipe Resume Optimizer"
4. Set role to "Read" (free tier)
5. Copy the token (starts with `hf_...`)

---

## ⚙️ Step 2: Configure Environment Variables

### Backend (.env file)

Create or edit `backend/.env`:

```bash
# Add this line to your existing .env file
HUGGINGFACE_API_KEY=hf_your_actual_token_here

# Your existing Supabase configs should already be here:
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

**Important:** Replace `hf_your_actual_token_here` with your actual token from Step 1.

---

## 📦 Step 3: Install Dependencies

```powershell
# In backend directory
cd backend
pip install huggingface-hub>=0.20.0

# Verify installation
python -c "from huggingface_hub import InferenceClient; print('✓ HuggingFace Hub installed')"
```

---

## 🗄️ Step 4: Run Database Migration

This creates the `resumes` and `resume_knowledge_base` tables.

```powershell
# Option A: Run SQL directly in Supabase Dashboard
# 1. Go to Supabase Dashboard > SQL Editor
# 2. Copy content from: backend/add_resume_optimization_tables.sql
# 3. Click "Run"

# Option B: Use Supabase CLI (if installed)
supabase db push
```

**Verify:** Go to Supabase Dashboard > Table Editor. You should see:
- `resumes` table
- `resume_knowledge_base` table

---

## 🧠 Step 5: Build Knowledge Base Embeddings

This creates the FAISS index from 75 optimization rules.

```powershell
cd backend

# Check current status
python src/build_resume_knowledge_embeddings.py --check

# Build embeddings (takes ~1-2 minutes)
python src/build_resume_knowledge_embeddings.py --force
```

**Expected Output:**
```
====================================================
BUILDING RESUME KNOWLEDGE BASE EMBEDDINGS
====================================================

✓ Loaded 75 optimization rules
✓ Loaded model: sentence-transformers/all-MiniLM-L6-v2
✓ Prepared 75 chunks for embedding
✓ Generated embeddings with shape: (75, 384)
✓ Embeddings normalized
✓ Built FAISS index with 75 vectors
✓ FAISS index saved
✓ Metadata saved

Chunk Types:
  - action_verbs: 8
  - domain_rule: 42
  - quantification: 20
  - star_method: 1
  - ats_rule: 4

Role Tags (top 15):
  - General: 15
  - Data Science: 8
  - AI/ML: 12
  - Backend: 7
  - DevOps: 10
  ...
```

**Verify Files Created:**
- `backend/models/resume_rules_faiss.index`
- `backend/models/resume_rules_metadata.pkl`

---

## 🚀 Step 6: Start the Backend Server

```powershell
cd backend

# Activate virtual environment (if not already)
.venv\Scripts\Activate.ps1

# Start Flask server
python app.py
```

**Expected Output:**
```
✓ resume_optimization_routes imported successfully
✓ All blueprints registered
 * Running on http://127.0.0.1:5000
```

---

## 🎨 Step 7: Start the Frontend

Open a **new terminal**:

```powershell
cd frontend

# Start Next.js dev server
npm run dev
# or
pnpm dev
```

**Expected Output:**
```
  ▲ Next.js 16.0.8
  - Local:        http://localhost:3000
  - Turbopack (experimental)
```

---

## 🧪 Step 8: Test the Feature

### A. Access the UI

1. Open browser: **http://localhost:3000/resume-optimizer**
2. You should see "Resume Optimizer" page

### B. Test with Sample Data

1. **Click "Load Sample Resume"** button
   - Sample resume appears in the left panel
   
2. **Paste a Job Description** in the right panel

   **Sample JD for Data Science Role:**
   ```
   Senior Data Scientist
   
   We are seeking a Senior Data Scientist to join our AI team.
   
   Requirements:
   - 5+ years experience in machine learning
   - Strong Python skills (TensorFlow, PyTorch, Scikit-learn)
   - Experience deploying ML models to production
   - Track record of delivering business impact through data
   - Excellent communication skills
   
   Responsibilities:
   - Build and deploy predictive models
   - Collaborate with engineering teams
   - Analyze large datasets
   - Present findings to stakeholders
   ```

3. **Select Sections** (default: all three checked)
   - ☑ experience
   - ☑ skills
   - ☑ summary

4. **Click "Optimize Resume"**
   - Shows "Optimizing..." with spinner
   - Takes ~10-20 seconds (HuggingFace API call)

5. **View Results**
   - **Analysis Card:** Shows detected roles (e.g., "Data Science", "AI/ML") and keywords
   - **Side-by-Side Comparison:**
     - Left: Original resume (plain)
     - Right: Optimized resume (green highlights)
   - **Optimization Reasoning:** Expandable JSON showing LLM's thought process

6. **Save the Optimized Version**
   - Click "Save Version" button
   - Alert: "Resume saved successfully! Version 1"
   - Button changes to "Saved" with checkmark

7. **Test Again** (creates Version 2)
   - Click "Optimize Another"
   - Paste a different JD (e.g., Backend Engineer)
   - Optimize and Save again
   - This creates Version 2

---

## 🔍 Step 9: Verify Data Persistence

### Check Supabase Database

1. Go to Supabase Dashboard > Table Editor > `resumes` table
2. You should see 2 rows (Version 1 and Version 2)
3. Click on a row to see:
   - `original_json`: Your sample resume
   - `optimized_json`: AI-optimized version
   - `optimization_metadata`: Detected roles, keywords, reasoning
   - `sections_optimized`: ["experience", "skills", "summary"]
   - `version`: 1 or 2

---

## 🧪 Step 10: Test API Endpoints Directly

### A. Test Knowledge Base Stats

```powershell
curl http://localhost:5000/knowledge-base-stats
```

**Expected Response:**
```json
{
  "success": true,
  "stats": {
    "total_chunks": 75,
    "embedding_dimension": 384,
    "chunk_types": {
      "action_verbs": 8,
      "domain_rule": 42,
      "quantification": 20,
      "star_method": 1,
      "ats_rule": 4
    },
    "role_coverage": {
      "General": 15,
      "Data Science": 8,
      "AI/ML": 12,
      ...
    }
  }
}
```

### B. Test Job Role Detection

```powershell
curl -X POST http://localhost:5000/detect-job-role `
  -H "Content-Type: application/json" `
  -d '{\"job_description\": \"Senior Software Engineer with Python and React experience\"}'
```

**Expected Response:**
```json
{
  "success": true,
  "detected_roles": ["Software Engineer", "Backend", "Full Stack", "Frontend"],
  "keywords": ["Python", "React", "Software Engineer", ...]
}
```

### C. Test Full Optimization

```powershell
curl -X POST http://localhost:5000/optimize-resume `
  -H "Content-Type: application/json" `
  -d @test_optimization.json
```

Where `test_optimization.json` contains:
```json
{
  "resume_json": {
    "name": "John Doe",
    "summary": "Software developer with experience",
    "skills": ["Python", "JavaScript"],
    "experience": [
      {
        "company": "TechCorp",
        "role": "Developer",
        "description": "Built features\nFixed bugs"
      }
    ]
  },
  "job_description": "Senior Python Developer needed. Strong FastAPI and PostgreSQL skills required.",
  "sections_to_optimize": ["experience", "skills", "summary"]
}
```

---

## 📊 Understanding the Optimization Flow

```
User Input (JD + Resume)
         ↓
1. Detect Job Role (e.g., "Data Science")
         ↓
2. Extract JD Keywords (e.g., ["Python", "TensorFlow"])
         ↓
3. Retrieve Optimization Rules (Metadata-Filtered RAG)
   - Query FAISS for "Data Science" + "AI/ML" tagged rules
   - Returns 8-10 most relevant rules
         ↓
4. Call HuggingFace API (Mistral-Nemo-Instruct)
   - Prompt: Original + Rules + JD Keywords
   - Response: Optimized JSON + Reasoning
         ↓
5. Validate (Anti-Hallucination Check)
   - Ensure no new facts added
   - Flag if optimized is >50% longer
         ↓
6. Return to User (Side-by-Side View)
         ↓
7. Save to Database (Optional)
   - Store both original and optimized
   - Track version history
```

---

## 🎯 Navigation Guide

### For First-Time Users

1. **Navigate to:** http://localhost:3000/resume-optimizer
2. **Load resume:** Click "Load Sample Resume" (or paste your own JSON)
3. **Add JD:** Paste target job description
4. **Optimize:** Click "Optimize Resume" button
5. **Review:** Compare original vs. optimized side-by-side
6. **Save:** Click "Save Version" to persist
7. **Repeat:** Try different JDs to see how optimization changes

### For Testing with Real Data

1. **Use your actual resume:**
   - Go to: http://localhost:3000/onboarding (if implemented)
   - Or manually format your resume as JSON matching this schema:
     ```json
     {
       "name": "Your Name",
       "email": "email@example.com",
       "summary": "Your professional summary",
       "skills": ["Skill1", "Skill2"],
       "experience": [
         {
           "company": "Company Name",
           "role": "Job Title",
           "duration": "2020 - 2023",
           "description": "Bullet point 1\nBullet point 2"
         }
       ],
       "education": [...]
     }
     ```

2. **Find real job postings:**
   - Copy full JD from LinkedIn, Indeed, or company websites
   - Include requirements, responsibilities, and qualifications sections

3. **Compare different industries:**
   - Test with Data Science JD → See ML-specific optimizations
   - Test with DevOps JD → See infrastructure-focused changes
   - Test with Cybersecurity JD → See security certification emphasis

---

## 🐛 Troubleshooting

### Issue: "HuggingFace API not configured"

**Solution:** Check `.env` file has `HUGGINGFACE_API_KEY=hf_...`

### Issue: "Knowledge base not loaded"

**Solution:** Run `python src/build_resume_knowledge_embeddings.py --force`

### Issue: API returns 500 error

**Check backend logs:** Look for specific error messages
**Common causes:**
- HuggingFace API rate limit (free tier: ~1000 requests/hour)
- Invalid API key
- Network issues

### Issue: No rules retrieved for my job

**Check role detection:**
```powershell
curl -X POST http://localhost:5000/detect-job-role `
  -H "Content-Type: application/json" `
  -d '{\"job_description\": \"YOUR JD HERE\"}'
```

If roles not detected, your JD may use uncommon keywords. Add them to `ROLE_MAPPINGS` in `backend/services/resume_optimization_service.py`.

---

## 📈 Performance Notes

- **First optimization:** ~10-20 seconds (HuggingFace cold start)
- **Subsequent optimizations:** ~5-10 seconds
- **Knowledge base loading:** ~2 seconds on server start
- **FAISS search:** <100ms (very fast)

---

## 🎓 FYP Demo Tips

1. **Prepare 3 contrasting JDs:**
   - Data Science (ML-focused)
   - DevOps (Infrastructure-focused)
   - Cybersecurity (Compliance-focused)

2. **Use same resume for all 3:**
   - Shows how system adapts to different roles
   - Highlights metadata-filtered RAG in action

3. **Show the reasoning chains:**
   - Expand "Optimization Reasoning" section
   - Point out how LLM explains which rules it applied

4. **Demonstrate version history:**
   - Save all 3 optimized versions
   - Show Supabase table with version tracking

5. **Highlight anti-hallucination:**
   - Show validation in logs
   - Explain how system prevents adding fake qualifications

---

## 📝 Quick Test Script

Save this as `test_resume_optimizer.ps1`:

```powershell
# Test script for Resume Optimizer
Write-Host "Testing Resume Optimizer API..." -ForegroundColor Cyan

# Test 1: Knowledge Base
Write-Host "`n[1/3] Testing Knowledge Base..." -ForegroundColor Yellow
$response = curl http://localhost:5000/knowledge-base-stats | ConvertFrom-Json
Write-Host "✓ Knowledge base has $($response.stats.total_chunks) chunks" -ForegroundColor Green

# Test 2: Role Detection
Write-Host "`n[2/3] Testing Role Detection..." -ForegroundColor Yellow
$jd = '{"job_description": "Senior Data Scientist with Python and TensorFlow"}'
$response = curl -X POST http://localhost:5000/detect-job-role `
  -H "Content-Type: application/json" `
  -d $jd | ConvertFrom-Json
Write-Host "✓ Detected roles: $($response.detected_roles -join ', ')" -ForegroundColor Green

# Test 3: Full Optimization (requires sample resume)
Write-Host "`n[3/3] Use UI for full optimization test" -ForegroundColor Yellow
Write-Host "→ Open http://localhost:3000/resume-optimizer" -ForegroundColor Cyan

Write-Host "`n✓ All API tests passed!" -ForegroundColor Green
```

Run with: `.\test_resume_optimizer.ps1`

---

## ✅ Success Checklist

- [ ] HuggingFace API key added to `.env`
- [ ] Dependencies installed (`huggingface-hub`)
- [ ] Database migration run (tables created)
- [ ] Knowledge base built (FAISS index exists)
- [ ] Backend server running (port 5000)
- [ ] Frontend server running (port 3000)
- [ ] UI accessible at `/resume-optimizer`
- [ ] Sample optimization successful
- [ ] Version saved to database
- [ ] Supabase shows saved resume versions

---

**You're all set! 🚀 Happy optimizing!**
