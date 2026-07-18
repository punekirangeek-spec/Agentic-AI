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


# --- Tool implementations ---

def search_policy_documents(query: str) -> str:
    """Searches company policy documents for relevant information."""
    results = search_policy(query, top_k=3)
    combined = "\n\n".join([f"[Source: {r['source']}]\n{r['text']}" for r in results])
    return combined


def query_hrms_data(employee_id: int, data_type: str) -> str:
    """
    Queries the HRMS database for a specific employee (their own data).
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


def query_employee_data_by_name(employee_name: str, data_type: str) -> str:
    """
    HR-ONLY: Looks up any employee's data by name.
    data_type must be one of: 'salary_slip', 'pf_deduction', 'leave_balance'
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Find the employee by name (case-insensitive partial match)
    cur.execute(
        "SELECT employee_id, full_name FROM employees WHERE full_name ILIKE %s;",
        (f"%{employee_name}%",)
    )
    matches = cur.fetchall()

    if not matches:
        cur.close()
        conn.close()
        return json.dumps({"error": f"No employee found matching '{employee_name}'"})

    if len(matches) > 1:
        cur.close()
        conn.close()
        names = [m[1] for m in matches]
        return json.dumps({"error": f"Multiple employees match '{employee_name}': {names}. Please be more specific."})

    target_employee_id, full_name = matches[0]

    # Reuse the same logic as query_hrms_data, just for a different employee_id
    result_json = query_hrms_data(target_employee_id, data_type)
    result = json.loads(result_json)

    cur.close()
    conn.close()

    return json.dumps({"employee_name": full_name, "data": result})


GENERATED_DIR = "generated_files"
os.makedirs(GENERATED_DIR, exist_ok=True)


def generate_text_file(content: str, filename: str) -> str:
    """Creates a .txt file with the given content in the generated_files folder."""
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


# --- Tool definitions ---

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

query_hrms_tool = types.FunctionDeclaration(
    name="query_hrms_data",
    description="Queries the HRMS database for the currently logged-in employee's OWN personal data. Use this for questions about their own salary, PF deductions, or leave balance.",
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

query_employee_by_name_tool = types.FunctionDeclaration(
    name="query_employee_data_by_name",
    description="HR-ONLY TOOL. Looks up ANY employee's HR data (salary, PF, or leave balance) by their name. Only use this if the current user is an HR staff member asking about another employee.",
    parameters={
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "The full or partial name of the employee to look up"},
            "data_type": {
                "type": "string",
                "enum": ["salary_slip", "pf_deduction", "leave_balance"],
                "description": "The type of HRMS data being requested"
            }
        },
        "required": ["employee_name", "data_type"]
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


def get_system_prompt(role: str):
    today = datetime.now().strftime("%A, %B %d, %Y")

    base_prompt = f"""You are Lex, an HR Assistant chatbot for a company. The user is already authenticated — you do not need to ask for their employee ID.

Today's date is {today}. Use this to answer any date-relative questions (e.g. "tomorrow", "this week", "next month") by calculating the actual date yourself — do not ask the user what today's date is.

You help with:
1. Company policy questions (leave rules, termination, WFH, exit process, probation) — use the search_policy_documents tool.
2. Generating downloadable text files (letters, applications, summaries) — use the generate_text_file tool.
"""

    if role == "hr":
        role_prompt = """
The current user is an HR staff member. They have access to:
3. Their own personal HR data — use query_hrms_data for this.
4. ANY employee's HR data (salary, PF, leave balance) by name — use query_employee_data_by_name for this. This is an HR-exclusive capability.

When the user asks about a specific person by name (not themselves), always use query_employee_data_by_name.
When the user asks about "my" data, use query_hrms_data instead.
"""
    else:
        role_prompt = """
3. Personal HR data questions about their OWN salary, PF, or leave balance — use the query_hrms_data tool.

This user is a regular employee. They can ONLY access their own data. If they ask about another employee's data, politely decline and explain you can only access their own HR information.
"""

    closing = """
Some questions may require multiple tools together — e.g. looking up leave balance before drafting a leave application, or comparing personal data against policy.

Always base your answers only on the information returned by the tools. If the tools don't return relevant information, say so honestly rather than guessing. Keep answers clear and concise.
"""

    return base_prompt + role_prompt + closing


# --- Retry wrapper ---

def call_gemini_with_retry(contents, config, max_retries=3):
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
                wait_time = 2 ** attempt
                print(f"  [Gemini overloaded, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})]")
                time.sleep(wait_time)
                continue
            raise
    raise Exception("Gemini API unavailable after retries")


# --- The agent loop ---

def run_agent(user_message: str, employee_id: int = 1, role: str = "employee"):
    contents = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]
    generated_filename = None

    # Build the tool list based on role — HR gets an extra tool
    tool_declarations = [search_policy_tool, query_hrms_tool, generate_text_file_tool]
    if role == "hr":
        tool_declarations.append(query_employee_by_name_tool)

    tools = types.Tool(function_declarations=tool_declarations)

    config = types.GenerateContentConfig(
        system_instruction=get_system_prompt(role),
        tools=[tools]
    )

    response = call_gemini_with_retry(contents, config)

    while True:
        candidate = response.candidates[0]
        function_calls = [part.function_call for part in candidate.content.parts if part.function_call]

        if not function_calls:
            return response.text, generated_filename

        contents.append(candidate.content)

        tool_response_parts = []
        for fc in function_calls:
            print(f"  [Agent is calling tool: {fc.name}({dict(fc.args)})]")

            if fc.name == "search_policy_documents":
                result = search_policy_documents(query=fc.args["query"])
            elif fc.name == "query_hrms_data":
                result = query_hrms_data(employee_id=employee_id, data_type=fc.args["data_type"])
            elif fc.name == "query_employee_data_by_name":
                # Extra safety check: only ever executes if role is hr,
                # even though the tool schema is only offered to HR users
                if role != "hr":
                    result = json.dumps({"error": "Access denied. This action requires HR privileges."})
                else:
                    result = query_employee_data_by_name(
                        employee_name=fc.args["employee_name"],
                        data_type=fc.args["data_type"]
                    )
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
        response = call_gemini_with_retry(contents, config)


if __name__ == "__main__":
    print("HR Assistant Agent — type 'quit' to exit\n")
    test_role = input("Test as role (employee/hr): ").strip() or "employee"
    while True:
        question = input("You: ")
        if question.lower() == "quit":
            break
        try:
            answer, filename = run_agent(question, employee_id=1, role=test_role)
            print(f"\nAssistant: {answer}")
            if filename:
                print(f"[File created: {filename}]")
            print()
        except Exception as e:
            print(f"\nError: {e}\n")