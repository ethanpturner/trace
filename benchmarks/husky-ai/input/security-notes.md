# Husky AI — Security Notes

The controls in place today, as maintained by the platform team. This document records
what is implemented; it does not list planned work.

## 1. Storage access control

Access control and authorization are configured on the Azure Blob storage accounts — the
training images, the model storage, and the source and configuration storage. Access is
granted per environment, and the production model blob is writable only from the
experimental deployment path and the Bastion.

## 2. Notebook access control

The Jupyter Notebook environment enforces access control and authorization. Engineers
authenticate before reaching any notebook, and the environment is not exposed outside the
experimental VPC.

## 3. Uploaded image handling

Uploaded images are held in memory in the Redis cache while awaiting classification, not
written to disk. In-memory storage was chosen to make user-submitted images difficult to
access after the request completes.

## 4. Administrative access logging

All SSH access attempts through the Bastion are logged to the Bastion Logs storage,
successful or not. The Bastion is the only administrative path into production.

## 5. Transport security

The public API is HTTPS-only. Image collection from Azure Cognitive Services uses TLS with
certificate validation.

## 6. Authentication summary

- Public to production: SSO.
- Public to experimental: password authentication.
- Production to experimental: public-key authentication.
- RBAC and ACLs at each boundary.
