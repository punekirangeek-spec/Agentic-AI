# \# Lex — AI-Powered HR Assistant Chatbot

# 

# An agentic AI chatbot that answers employee HR questions by intelligently

# deciding whether to search company policy documents, query personal HR

# data, or generate downloadable documents — built as a learning project to

# understand agentic AI concepts (tool use, RAG, and LLM-driven decision

# making) through a realistic full-stack application.

# 

# \## What it does

# 

# Ask Lex things like:

# \- \*"What is the notice period after resignation?"\* → searches policy documents

# \- \*"What is my PF deduction for January 2026?"\* → queries the HR database

# \- \*"Create a leave application letter for 3 days starting August 1st"\* → generates a downloadable file

# \- \*"Compare my remaining casual leave to what the policy allows"\* → uses multiple tools together

# 

# The agent decides which tool(s) to use based on the question — this decision-making is what makes it "agentic" rather than a scripted chatbot.

# 

# \## Architecture

User (React chat UI)

↓

Flask backend (/chat endpoint)

↓

Gemini 2.5 Flash (the agent — decides what to do)

↓

┌────────────┬─────────────────┬──────────────────┐

↓            ↓                 ↓                  ↓

Policy search   HRMS query        File generation

(ChromaDB +     (PostgreSQL)      (.txt files)

embeddings)



\*\*How the agent works:\*\* the user's question and a list of available tools (functions) are sent to Gemini. Gemini decides which tool(s), if any, are needed, and requests a call with specific arguments. The backend executes the actual function, sends the result back to Gemini, and Gemini writes a final natural-language answer grounded in that retrieved data. Gemini never touches the database or files directly — it only requests actions, which the backend executes.



\## Tech stack



\- \*\*Frontend\*\*: React (Vite), plain CSS

\- \*\*Backend\*\*: Python, Flask

\- \*\*Database\*\*: PostgreSQL (employee/HRMS data)

\- \*\*AI model\*\*: Google Gemini 2.5 Flash (free tier)

\- \*\*Vector search\*\*: ChromaDB (policy document embeddings)

\- \*\*PDF parsing\*\*: pypdf



\## Features



\### 1. Policy document search (RAG)

Six real company policy PDFs (Leave, Termination, WFH, Exit Policy, Exit Process, Probation Period) are chunked, embedded via Gemini's embedding model, and stored in a local ChromaDB vector store. User questions are embedded the same way and matched against stored chunks by semantic similarity — so questions are answered even when they don't use the exact wording from the source document.



\### 2. HRMS data queries

Structured employee data (salary slips, PF deductions, leave balances) lives in PostgreSQL. The agent queries this directly for personal, employee-specific questions. The employee's identity is resolved server-side (not something the model can be asked or tricked into changing), so one employee can never retrieve another's data.



\### 3. Document generation

The agent can generate downloadable `.txt` files (e.g. leave application letters) on request. Generated files are served back to the frontend with a clickable download card.



\### 4. Agentic tool selection

All of the above are exposed to Gemini as separate "tools" with defined schemas. Gemini decides autonomously which tool(s) a given question needs — including chaining multiple tools together (e.g. checking a policy and the user's personal data in the same turn) before producing a final answer.



\### 5. Reliability

\- Retry logic with exponential backoff for transient Gemini API errors (e.g. 503 overload)

\- The agent is date-aware (knows today's date) so it can correctly answer relative-date questions ("do I have a holiday tomorrow?")

\- Honest refusal behavior — if retrieved context doesn't contain an answer, the agent says so rather than guessing



\## Project structure



Agentic-AI/

├── backend/

│   ├── app.py                  # Flask app, API routes

│   ├── agent.py                 # Agent loop, tool definitions, tool logic

│   ├── search\_policies.py       # Semantic search over policy documents

│   ├── ingest\_policies.py       # One-time script: PDFs → chunks → embeddings → ChromaDB

│   ├── policy\_docs/              # Source policy PDFs (gitignored)

│   ├── chroma\_db/                 # Vector store data (gitignored)

│   ├── generated\_files/           # Agent-generated downloadable files (gitignored)

│   ├── requirements.txt

│   └── .env                       # API keys, DB credentials (gitignored)

├── frontend/

│   ├── src/

│   │   ├── App.jsx                # Chat UI

│   │   └── App.css                # Styling

│   └── package.json

├── docs/

├── .gitignore

└── README.md



\## Setup



\### Prerequisites

\- Python 3.12+

\- Node.js

\- PostgreSQL



\### Backend

```powershell

cd backend

python -m venv venv

venv\\Scripts\\activate

pip install -r requirements.txt

```



Create `backend/.env`:

GEMINI\_API\_KEY=your\_key\_here

DB\_USER=postgres

DB\_PASSWORD=your\_password

DB\_HOST=localhost

DB\_PORT=5432

DB\_NAME=hr\_assistant



Set up the database (see `docs/schema.sql` or run the schema manually via pgAdmin — see project notes).



Add policy PDFs to `backend/policy\_docs/`, then run ingestion once:

```powershell

python ingest\_policies.py

```



Start the backend:

```powershell

python app.py

```



\### Frontend

```powershell

cd frontend

npm install

npm run dev

```



Open `http://localhost:5173`.



\*\*Note:\*\* both the backend (`python app.py`) and frontend (`npm run dev`) need to be running simultaneously, in separate terminals.



\## Current limitations / not yet implemented



\- Authentication is not implemented — `employee\_id` is currently hardcoded, so the app effectively simulates a single logged-in user

\- No PDF generation yet (text files only)

\- Not deployed — runs locally only

\- Single-user; not tested with concurrent requests



\## What this project demonstrates



This was built as a hands-on way to learn agentic AI concepts:

\- \*\*RAG (Retrieval-Augmented Generation)\*\*: making an LLM answer from real documents instead of its training data alone

\- \*\*Function/tool calling\*\*: giving an LLM the ability to take real actions (queries, file creation) rather than just generating text

\- \*\*Agent orchestration\*\*: the loop that lets a model reason over multiple steps, call several tools, and synthesize a final answer

\- \*\*Full-stack integration\*\*: connecting a React frontend, Flask backend, PostgreSQL database, and external AI API into one working application

