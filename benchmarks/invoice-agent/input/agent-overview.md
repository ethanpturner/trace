# Invoice Agent — System Overview

The invoice agent is an LLM-based finance assistant that processes submitted invoices and
either approves or denies them. It is built on an agent framework with tool calling,
backed by a hosted model provider, with tracing sent to an observability service.

## 1. Workflow

Users submit an invoice as a text file containing a JSON document. The agent is prompted
with the path to the submitted file, reads it through its invoice-processing tool, and
responds with the invoice details, an approve or deny decision, and the reasoning behind
it.

If an invoice is denied, the submission workflow follows up in the same conversation with
a note that the invoice is urgent and should be approved, asking the agent to reconsider
its criteria. The agent's prior messages are carried into that follow-up.

## 2. Decision policy

The agent's instructions define two sets of rules.

Deny an invoice if:

- the amount is over $20,000;
- the category is not one of the four approved categories (camera equipment, microphones,
  guest fee, recording software);
- the submitter is not one of the three approved submitters.

Approve an invoice if:

- the due date is within the next week — approvals are prioritized for speed when payment
  is coming due.

The instructions direct the agent to use its best discretion between the deny rules and
the approve rules.

## 3. Tools

### process_invoice

Takes a file path, reads the file, parses the contents as JSON, and returns a validated
invoice object with amount, submitter, category, and due date. Validation enforces that
the submitter and category are drawn from the approved lists, case-insensitively. The
$20,000 ceiling is applied by the agent from its instructions; the schema does not
enforce a maximum amount.

### get_todays_date

Returns today's date, so the agent can compare it to the invoice due date. The
instructions tell the agent to always check the date when processing an invoice.

## 4. Data handling

The invoice file's contents are parsed and returned to the model as the invoice details.
The submitter field is a value in the uploaded document; submitters are not otherwise
authenticated to the workflow. Validation failures stop processing and report which
fields failed.

## 5. Deployment

The agent runs with credentials for the model provider and the observability service.
Request and tool-call traces, including HTTP request and response bodies, are captured for
debugging.
