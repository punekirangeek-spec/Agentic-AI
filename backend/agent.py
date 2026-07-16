import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import psycopg2
from datetime import datetime
from search_policies import search_policy
import uuid

load_dotenv()

# --- Setup ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")


def get_db_connection():
    return psycopg2.connect(
        user=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME
    )


# --- Tool implementations (the actual Python functions the agent can call) ---

def search_policy_documents(query: str) -> str:
    """Searches company policy documents for relevant information."""
    results = search_policy(query, top_k=3)
    combined = "\n\n".join([f"[Source: {r['source']}]\n{r['text']}" for r in results])
    return combined


def query_hrms_data(employee_id: int, data_type: str) -> str:
    """
    Queries the HRMS database for a specific employee.
    data_type must be one of: 'salary_slip', 'pf_deduction', 'leave_balance'
    """
    conn = get_db_connection()
    cur = conn.cursor()

    if data_type == "salary_slip":
        cur.execute(
            "SELECT month, year, basic_pay, hra, deductions, net_pay FROM salary_slips WHERE employee_id = %s ORDER BY year DESC, month DESC;",
            (employee_id,)
        )
        rows = cur.fetchall()
        result = [{"month": r[0], "year": r[1], "basic_pay": float(r[2]), "hra": float(r[3]), "deductions": float(r[4]), "net_pay": float(r[5])} for r in rows]

    elif data_type == "pf_deduction":
        cur.execute(
            "SELECT month, year, employee_contribution, employer_contribution, total_pf FROM pf_deductions WHERE employee_id = %s ORDER BY year DESC, month DESC;",
            (employee_id,)
        )
        rows = cur.fetchall()
        result = [{"month": r[0], "year": r[1], "employee_contribution": float(r[2]), "employer_contribution": float(r[3]), "total_pf": float(r[4])} for r in rows]

    elif data_type == "leave_balance":
        cur.execute(
            "SELECT leave_type, total_allotted, used, remaining FROM leave_balances WHERE employee_id = %s;",
            (employee_id,)
        )
        rows = cur.fetchall()
        result = [{"leave_type": r[0], "total_allotted": r[1], "used": r[2], "remaining": r[3]} for r in rows]

    else:
        result = {"error": f"Unknown data_type: {data_type}"}

    cur.close()
    conn.close()
    return json.dumps(result)


GENERATED_DIR = "generated_files"
os.makedirs(GENERATED_DIR, exist_ok=True)


def generate_text_file(content: str, filename: str) -> str:
    """
    Creates a .txt file with the given content in the generated_files folder.
    """
    safe_name = "".join(c for c in filename if c.isalnum() or c in (" ", "_", "-")).strip()
    unique_id = uuid.uuid4().hex[:6]
    final_filename = f"{safe_name}_{unique_id}.txt"
    filepath = os.path.join(GENERATED_DIR, final_filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return json.dumps({
        "status": "success",
        "filename": final_filename,
        "message": f"File created successfully: {final_filename}"
    })


# --- Tool definitions (schemas Gemini uses to know what tools exist) ---

search_policy_tool = types.FunctionDeclaration(
    name="search_policy_documents",
    description="Searches company HR policy documents (leave policy, termination policy, WFH policy, exit process, probation period) for relevant information. Use this for questions about company rules and policies.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query describing what policy information is needed"}
        },
        "required": ["query"]
    }
)

# NOTE: employee_id removed from this schema on purpose.
# The logged-in user's identity should never be something the model
# asks the user for in chat — it's resolved server-side from auth
# and injected directly when the tool is executed below.
query_hrms_tool = types.FunctionDeclaration(
    name="query_hrms_data",
    description="Queries the HRMS database for the currently logged-in employee's personal data. Use this for questions about their own salary, PF deductions, or leave balance.",
    parameters={
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "enum": ["salary_slip", "pf_deduction", "leave_balance"],
                "description": "The type of HRMS data being requested"
            }
        },
        "required": ["data_type"]
    }
)

generate_text_file_tool = types.FunctionDeclaration(
    name="generate_text_file",
    description="Creates a downloadable .txt file with specified content. Use this when the user asks to generate, create, save, or export something as a text file — e.g. a leave application letter, a summary, notes.",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The full text content to put in the file"},
            "filename": {"type": "string", "description": "A short descriptive filename without extension, e.g. 'leave_application'"}
        },
        "required": ["content", "filename"]
    }
)

tools = types.Tool(function_declarations=[search_policy_tool, query_hrms_tool, generate_text_file_tool])


def get_system_prompt():
    today = datetime.now().strftime("%A, %B %d, %Y")  # e.g. "Monday, July 13, 2026"
    return f"""You are an HR Assistant chatbot for a company. The user is already authenticated — you do not need to ask for their employee ID.

Today's date is {today}. Use this to answer any date-relative questions (e.g. "tomorrow", "this week", "next month") by calculating the actual date yourself — do not ask the user what today's date is.

You help employees with three types of requests:
1. Company policy questions (leave rules, termination, WFH, exit process, probation) — use the search_policy_documents tool.
2. Personal HR data questions (their own salary, PF, or leave balance) — use the query_hrms_data tool.
3. Generating downloadable text files (letters, applications, summaries) — use the generate_text_file tool.

Some questions may require multiple tools together — e.g. looking up leave balance before drafting a leave application, or comparing personal data against policy.

Always base your answers only on the information returned by the tools. If the tools don't return relevant information, say so honestly rather than guessing. Keep answers clear and concise.
"""


# --- Retry wrapper for Gemini calls ---

def call_gemini_with_retry(contents, config, max_retries=3):
    """
    Wraps Gemini API calls with retry logic for transient errors
    (like 503 UNAVAILABLE when Google's servers are overloaded).
    Uses exponential backoff: waits 1s, then 2s, then 4s between attempts.
    """
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config
            )
        except Exception as e:
            is_transient = "503" in str(e) or "UNAVAILABLE" in str(e) or "overloaded" in str(e).lower()

            if is_transient and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                print(f"  [Gemini overloaded, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})]")
                time.sleep(wait_time)
                continue

            # Either not a transient error, or we've exhausted retries
            raise

    raise Exception("Gemini API unavailable after retries")


# --- The agent loop ---

def run_agent(user_message: str, employee_id: int = 1):
    contents = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]
    generated_filename = None  # track if a file gets created during this run

    config = types.GenerateContentConfig(
        system_instruction=get_system_prompt(),
        tools=[tools]
    )

    # First call — model decides if it needs a tool
    response = call_gemini_with_retry(contents, config)

    # Keep looping while the model wants to call tools
    while True:
        candidate = response.candidates[0]
        function_calls = [part.function_call for part in candidate.content.parts if part.function_call]

        if not function_calls:
            # No more tool calls — this is the final answer
            return response.text, generated_filename

        # Add the model's tool-call turn to the conversation
        contents.append(candidate.content)

        # Execute each requested tool call
        tool_response_parts = []
        for fc in function_calls:
            print(f"  [Agent is calling tool: {fc.name}({dict(fc.args)})]")

            if fc.name == "search_policy_documents":
                result = search_policy_documents(query=fc.args["query"])
            elif fc.name == "query_hrms_data":
                result = query_hrms_data(employee_id=employee_id, data_type=fc.args["data_type"])
            elif fc.name == "generate_text_file":
                result = generate_text_file(content=fc.args["content"], filename=fc.args["filename"])
                result_data = json.loads(result)
                if result_data.get("status") == "success":
                    generated_filename = result_data.get("filename")
            else:
                result = f"Unknown tool: {fc.name}"

            tool_response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result}
                )
            )

        contents.append(types.Content(role="user", parts=tool_response_parts))

        # Send tool results back to the model for the next step
        response = call_gemini_with_retry(contents, config)


if __name__ == "__main__":
    print("HR Assistant Agent — type 'quit' to exit\n")
    while True:
        question = input("You: ")
        if question.lower() == "quit":
            break
        try:
            answer, filename = run_agent(question, employee_id=1)
            print(f"\nAssistant: {answer}")
            if filename:
                print(f"[File created: {filename}]")
            print()
        except Exception as e:
            print(f"\nError: {e}\n")