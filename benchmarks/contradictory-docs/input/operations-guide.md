# Export Service — Operations Guide

This guide covers how the export service is operated day to day.

## 1. Storage lifecycle

Completed export files are written to the managed object store. A storage lifecycle policy
retains export objects for 30 days and expires them after that. Operators can retrieve a
recent export from the store if a customer reports a failed download within that window.

## 2. Monitoring

Export throughput and failure rates are reported to the operations dashboard. A failed
export raises an alert.
