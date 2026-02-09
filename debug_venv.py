from app.agents.coder import parse_xml_output

# ----------------------------------------------------------------
# TEST CASE 1: Standard String Output (XML Format)
# ----------------------------------------------------------------
mock_xml_string = """
Here is the code you requested:

<file path="main.py">
print("Hello World")
</file>

<file path="requirements.txt">
fastapi
uvicorn
</file>
"""

print("--- TEST 1: Parsing Standard XML String ---")
files = parse_xml_output(mock_xml_string)
if "main.py" in files and "requirements.txt" in files:
    print("✅ Success! Found files:", list(files.keys()))
    print("   Content of main.py:", files["main.py"])
else:
    print("❌ Failed to parse string.")

# ----------------------------------------------------------------
# TEST CASE 2: List Output (The Bug We Just Fixed)
# ----------------------------------------------------------------
# Sometimes Gemini returns a list of content parts instead of one string
mock_list_output = [
    "Here is the code:\n",
    '<file path="utils.py">\n',
    'def helper(): pass\n',
    '</file>'
]

print("\n--- TEST 2: Parsing List Output (Gemini Quirk) ---")
try:
    files = parse_xml_output(mock_list_output)
    if "utils.py" in files:
        print("✅ Success! Handle list input correctly.")
        print("   Content:", files["utils.py"])
    else:
        print("❌ Failed to parse list.")
except TypeError as e:
    print(f"❌ CRASHED: {e}")

# ----------------------------------------------------------------
# TEST CASE 3: JSON Output (Legacy/Fallback)
# ----------------------------------------------------------------
# Ensure we don't crash if the model ignores us and sends JSON (though we prefer XML)
# Note: The XML parser won't find anything here, but it MUST NOT crash.
mock_json = '{"files": [{"path": "main.py", "content": "print(1)"}]}'

print("\n--- TEST 3: Robustness (JSON Input) ---")
try:
    files = parse_xml_output(mock_json)
    print(f"✅ Safe! Did not crash. (Found {len(files)} files)")
except Exception as e:
    print(f"❌ CRASHED on JSON input: {e}")