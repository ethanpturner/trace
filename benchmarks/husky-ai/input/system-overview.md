# Husky AI — System Overview

Husky AI is a machine learning system that classifies uploaded images as huskies or
non-huskies. A convolutional neural network is trained on collected images, packaged, and
served behind a public API. This document describes the architecture as deployed.

## 1. Environments

The system runs in two internal Azure VPCs plus the public internet:

- **Production** — the deployed model and everything that serves it: the API Gateway, the
  Python web server, the Bastion server, and the production storage accounts.
- **Experimental** — model development: the image-gathering application, the Jupyter
  Notebook environment, and the deployment service, with the training data and source
  storage.
- **Public internet** — end users, Azure Cognitive Services, and the third-party tools the
  experimental environment pulls from.

Access across the public-to-production boundary is authenticated with SSO. Access across
the public-to-experimental boundary is password-authenticated. Movement between the
production and experimental environments uses public-key authentication, with RBAC and
ACLs applied at each boundary.

## 2. Components

### API Gateway (production)

The entry point for external users, exposed over HTTPS. It routes user requests to the
Python web server, enforces request validation, and manages the APIs exposed to the public
while ensuring access control to internal services.

### Simple Python Web Server (production)

Serves the classification application. It loads the trained model from the model storage
blob and evaluates uploaded images against it.

### Bastion Server (production)

The administrative access path into production. Administrators reach production hosts over
SSH through the Bastion; it reads authorized keys from the Authorized Keys storage and
writes access logs to a dedicated log store. The deployment service also delivers releases
into production through the Bastion.

### Gather Images Application (experimental)

A Python application that collects husky and non-husky images from Azure Cognitive
Services and third-party tools, using API keys held in the API key store, and writes them
to the training images blob.

### Jupyter Notebook (experimental)

The model development environment. Notebooks read the training and validation images,
train the convolutional neural network, and write the serialized model to the model
storage blob.

### Deployment Service (experimental)

Packages the trained model together with source code and configuration from the source
storage and deploys the result to production via the Bastion.

## 3. Data stores

| Store | Environment | Contents |
| --- | --- | --- |
| Training and Validation Images blob | Experimental | Images used for training and validation |
| API Key storage | Experimental | API keys for the external image services |
| Source Code and Configuration storage | Experimental | Source and configuration used by deployment |
| Machine Learning Model blob | Production | Trained models in serialized form |
| Authorized Keys storage | Production | SSH keys authorizing administrative access |
| Bastion Logs storage | Production | SSH access and activity logs from the Bastion |
| Azure Cache for Redis | Production | In-memory store for uploaded images awaiting classification |

## 4. Data flows

Training path: Azure Cognitive Services and third-party tools supply images to the Gather
Images application, which writes them to the training images blob. The Jupyter environment
reads those images, and engineers work in it directly. The trained model is written to the
model blob, from which the deployment service packages releases and delivers them through
the Bastion into production.

Serving path: an end user submits an image to the API Gateway over HTTPS. The gateway
forwards the request to the Python web server, which holds the uploaded image in the Redis
cache, evaluates it against the loaded model, and returns the classification.

Administrative path: platform engineers SSH to the Bastion, which authenticates them
against the Authorized Keys storage, logs the session to the Bastion Logs storage, and
provides onward access to the API Gateway, the web server, and the model blob.

Images are fetched from Azure Cognitive Services over TLS, with server certificates
validated during transmission.

## 5. Actors

- **End users** — submit images for classification through the public API.
- **Data engineers** — build, train, and deploy the models; work in the experimental
  environment.
- **Azure platform engineers** — secure and maintain the production infrastructure;
  administrative access is through the Bastion.
- **Azure Cognitive Services and third-party tools** — external services supplying
  training images.
