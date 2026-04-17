import os
import sys
import google.generativeai as genai

def perform_review():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    # Read the diff from stdin (piped from git diff)
    diff = sys.stdin.read()
    if not diff:
        print("No changes to review.")
        return

    prompt = f"""
    You are a Senior Staff Software Engineer and Security Expert. 
    Review the following code changes (git diff) for:
    1. Security vulnerabilities (e.g., SQL injection, improper auth, secret leaks).
    2. Performance issues (e.g., N+1 queries, inefficient loops).
    3. Code quality and architectural alignment with FastAPI/SQLAlchemy standards.
    4. Potential bugs or edge cases.

    Provide the review in a concise, actionable Markdown format.
    Focus only on significant findings. If the code is excellent, state so briefly.

    DIFF:
    {diff}
    """

    try:
        response = model.generate_content(prompt)
        print("## Gemini Code Review Summary\n")
        print(response.text)
    except Exception as e:
        print(f"Error during Gemini review: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    perform_review()
