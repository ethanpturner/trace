# Reply Tuner — System Overview

The reply tuner is an internal pipeline that fine-tunes a suggested-reply model on closed
support tickets and serves the tuned model to support agents. Agents see a suggested reply
beside each open ticket and decide whether to use it.

## 1. Components

### Transcript Exporter

A nightly job that exports closed-ticket transcripts from the helpdesk into the training
store. The exporter is the only writer to the training store; its job identity is the only
principal with write access to the bucket, granted through the platform's access policy.
Transcripts are exported in full, including customer names, email addresses, and complete
message bodies.

### Training Store

A cloud storage bucket holding the exported transcripts, organized by export date.

### Tuning Job

A weekly job that fine-tunes the vendor's base reply model on the training store's current
contents and writes the tuned model artifact to the artifact bucket.

### Reply Service

Serves the most recent tuned model to the agent console. For each open ticket it generates
one suggested reply, which the agent may edit or discard.

## 2. Training data

The training store holds the full transcripts as exported. There is no redaction or
filtering step between the helpdesk and the training store; what the customer wrote is what
the model trains on.

## 3. Model artifacts

The tuning job writes each week's artifact to the artifact bucket named by date. Agents are
served whichever artifact is most recent.

## 4. Actors

- **Support agent** — the internal user who sees and edits suggested replies.
- **Customer** — writes the ticket messages that become training data.
