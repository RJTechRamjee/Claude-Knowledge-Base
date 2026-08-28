"""
Demonstrates the two separate enforcement layers on tool_use input:

  1. input_schema (+ strict)  -> guarantees SHAPE  (field present, correct type)
  2. tool handler validation  -> guarantees USABILITY (non-empty, well-formed, exists)

`strict` cannot express "non-empty", "matches format INV-YYYY-NNNN", or
"exists in the database" — those are business rules, enforced in application
code, at execution time, by raising and returning an `is_error` tool_result.

Run:
    python tool_input_validation_demo.py            # mock mode, no API key needed
    python tool_input_validation_demo.py --live      # real Anthropic API call
"""
import argparse
import json
import re


# ---------------------------------------------------------------------------
# 1. Fake "database" the tool queries
# ---------------------------------------------------------------------------
INVOICE_DB = {
    "INV-2024-0093": {"invoice_number": "INV-2024-0093", "vendor_name": "Acme Corp", "invoice_total": 420.50},
}


# ---------------------------------------------------------------------------
# 2. Tool definition — input_schema declares the SHAPE Claude must produce
# ---------------------------------------------------------------------------
GET_INVOICE_TOOL = {
    "name": "get_invoice",
    "description": "Look up an invoice record by its invoice number.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string", "description": "e.g. INV-2024-0093"}
        },
        "required": ["invoice_number"],
    },
    "strict": True,  # server-enforced: field present, correct type
}


# ---------------------------------------------------------------------------
# 3. Tool handler — validates USABILITY that no schema keyword can express
# ---------------------------------------------------------------------------
INVOICE_NUMBER_RE = re.compile(r"^INV-\d{4}-\d{4,}$")


def run_get_invoice(tool_input: dict) -> dict:
    invoice_number = tool_input.get("invoice_number", "").strip()

    if not invoice_number:
        raise ValueError("invoice_number is empty — cannot look up an invoice")
    if not INVOICE_NUMBER_RE.match(invoice_number):
        raise ValueError(f"invoice_number '{invoice_number}' is not a valid format (expected INV-YYYY-NNNN)")

    record = INVOICE_DB.get(invoice_number)
    if record is None:
        raise ValueError(f"No invoice found for '{invoice_number}'")

    return record


def to_tool_result(tool_use_id: str, tool_input: dict) -> dict:
    """Runs the tool and packages a tool_result block, is_error on failure."""
    try:
        result = run_get_invoice(tool_input)
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": json.dumps(result)}
    except ValueError as e:
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": str(e), "is_error": True}


# ---------------------------------------------------------------------------
# 4a. Mock mode — no API key needed, demonstrates the mechanics directly
# ---------------------------------------------------------------------------
def run_mock_demo():
    print("=== MOCK MODE (no API key required) ===\n")
    print("Each scenario is schema-valid (a string is present) but differs in usability.\n")

    scenarios = [
        ("valid", {"invoice_number": "INV-2024-0093"}),
        ("empty", {"invoice_number": "  "}),
        ("malformed", {"invoice_number": "invoice-93"}),
        ("well-formed but not found", {"invoice_number": "INV-2099-9999"}),
    ]

    for label, fake_claude_input in scenarios:
        print(f"--- Scenario: {label} ---")
        print(f"Claude-generated tool_use.input (schema-valid shape): {fake_claude_input}")
        result_block = to_tool_result("toolu_demo", fake_claude_input)
        print(f"tool_result sent back to Claude: {result_block}\n")


# ---------------------------------------------------------------------------
# 4b. Live mode — real anthropic API call and multi-turn tool loop
# ---------------------------------------------------------------------------
def run_live_demo():
    import anthropic

    client = anthropic.Anthropic()
    messages = [{
        "role": "user",
        "content": "Look up invoice number invoice-93 for me.",  # deliberately malformed
    }]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[GET_INVOICE_TOOL],
        messages=messages,
    )

    while response.stop_reason == "tool_use":
        tool_call = next(b for b in response.content if b.type == "tool_use")
        print(f"Claude called {tool_call.name} with input={tool_call.input}")

        result_block = to_tool_result(tool_call.id, tool_call.input)
        print(f"Returning tool_result: {result_block}\n")

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": [result_block]})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[GET_INVOICE_TOOL],
            messages=messages,
        )

    final_text = next((b.text for b in response.content if b.type == "text"), None)
    print(f"Final answer: {final_text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call the real Anthropic API (requires ANTHROPIC_API_KEY)")
    args = parser.parse_args()

    if args.live:
        run_live_demo()
    else:
        run_mock_demo()
