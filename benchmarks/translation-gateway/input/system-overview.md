# Helpdesk Translate — System Overview

Helpdesk Translate lets support agents translate customer tickets in place. It is a
connector service between the helpdesk and an external translation SaaS.

## 1. Workflow

An agent opens a ticket and selects translate. The connector sends the full ticket body —
including any customer-written text and the extracted text of customer attachments — to the
translation provider over HTTPS, and writes the returned translation back onto the ticket
as an internal note.

## 2. Integration

The connector authenticates to the helpdesk with a workspace API token. The token grants
full workspace access; it was scoped that way during setup because it was convenient, and
the integration only reads tickets and writes notes.

## 3. Data handling

No agreement covering the translation provider's retention of submitted text, or its use of
submitted text for any purpose beyond returning the translation, has been established. The
provider's standard terms apply; they have not been reviewed for this integration.
