# Autonomous Self-Healing Data Engineering Agent

An advanced, dataset-agnostic Multi-Agent Text-to-SQL execution pipeline built using **LangGraph (Cyclic State Primers)** and **Gemini**, integrated directly with live **Google BigQuery** cloud data warehouses.

Unlike static Text-to-SQL implementations that crash on schema mismatch or hallucinated syntax, this system relies on automated runtime discovery, proactive token pruning, pre-execution dry runs, and a stateful exception-handling self-healing loop.

---

## 🚀 Key Engineering Core Features

* **Dynamic Schema Context Pruning:** At runtime, the system queries the target database's `INFORMATION_SCHEMA.TABLES` path. An LLM acts as a semantic filter to select only the tables relevant to the user query. The agent then dynamically queries `INFORMATION_SCHEMA.COLUMNS` for only those targeted tables—minimizing prompt token usage and preserving context efficiency.
* **Deterministic Fault Tolerance (Self-Healing Loop):** When query execution throws an engine exception, a validator node intercepts the cloud error traceback, writes it to the central graph state, and loops execution seamlessly back to the generation engine for autonomous debugging.
* **Cost & Performance Guardrails:** The agent performs a pre-execution `dry_run` validation check to evaluate `total_bytes_processed` and catch catastrophic bottlenecks (such as full table scans) before any compute costs are billed to the production project.
* **Durable Session Persistence:** Volatile in-memory graph state is replaced with a persistent, file-backed `SqliteSaver` checkpointer. This separates conversations by `thread_id`, providing complete session retention and enabling time-travel debugging across system restarts.

---

## 🏗️ Architecture Design

The system maps execution state variables through a cyclic multi-agent workflow:

1. **User Request:** Project ID, Dataset ID, and a Natural Language Query are entered via a terminal dashboard.
2. **Planner Node:** Discovers available tables live, uses a structured LLM call to select relevant targets, and pulls column details to build a focused schema map.
3. **Engineer Node:** Synthesizes SQL dynamically qualified for the target data warehouse. If a historical error is present in the graph state, it reflects on the error traceback logs to fix the query.
4. **Validator Node:** Executes a dry run config profile. If it fails, it increments the retry counter and routes back to the Engineer. If it passes, it pulls data natively into clean lists of dictionaries.

---

## 🛠️ Project Directory Tree

```text
├── src/
│   ├── __init__.py
│   ├── config.py          # Centralized Gemini LLM configuration initialization
│   ├── state.py           # Type-safe GraphState definitions via TypedDict
│   ├── database.py        # BigQuery execution sandbox engine & dry-run handlers
│   ├── tools.py           # INFORMATION_SCHEMA discovery metadata utilities
│   └── agent.py           # Node definitions, conditional routing logic, & compilation
├── .env.template          # Standard template for API variables
├── requirements.txt       # Pinned production library configurations
└── main.py                # Visual terminal streaming interface entry point

```

---

## ⚙️ Installation & Workspace Setup

### 1. Clone the Project & Set Up Virtual Environment

```bash
git clone <your-github-repo-url>
cd <repo-name>
python -m venv .venv
source .venv/Scripts/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

```

### 2. Configure Environment Variables

Create a `.env` file in the root folder matching this layout:

```ini
GOOGLE_API_KEY=your_gemini_api_key_here
BIGQUERY_PROJECT_ID=your_local_gcp_billing_project_id
GOOGLE_APPLICATION_CREDENTIALS=gcp-credentials.json

```

### 3. Place GCP Service Account Credentials

Generate a JSON Private Key file for a Service Account with **BigQuery Admin** clearance in your Google Cloud Console. Drop the file in the project root and name it `gcp-credentials.json`.

---

## 📊 Verification & Execution

Run the streamed CLI application dashboard:

```bash
python main.py

```

### Prompt Input Test Cases:

```text
Target GCP Project ID: bigquery-public-data
Target Dataset ID: thelook_ecommerce
Natural Language Query: Show the names and IDs of the top 3 distribution centers with the highest inventory levels.

```

The system will stream the workflow updates live in your terminal, detailing table mapping, token optimization steps, any encountered runtime anomalies, self-corrections, and the final analytical data output.

```

---

## 3. The Terminal Workflow to Push to GitHub

Once your files are saved, run these exact commands in your VS Code terminal to initialize Git and push your project to a new repository:

```bash
# 1. Initialize local git repository
git init

# 2. Add all tracked files (your .gitignore will automatically hide your secrets)
git add .

# 3. Double check that no secrets are staged (you should NOT see .env or json files)
git status

# 4. Commit your initial framework code
git commit -m "feat: complete dynamic self-healing multi-agent bigquery agent engine using langgraph and gemini"

# 5. Create a main branch
git branch -M main

# 6. Link to your new remote GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 7. Push to your repository
git push -u origin main

```

Your project is completely polished, documented, and secure. Once it is uploaded, your portfolio repository is ready to be shared with potential employers or clients. Let me know if you run into any issues during the upload workflow!
