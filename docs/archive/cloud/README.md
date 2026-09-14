# Archived cloud deployment

Cloud deployment is not part of the supported local workflow. These files are
preserved for reference and are not active GitHub Actions or Cloud Build inputs.
The old pipeline was introduced in December 2025 to deploy to Cloud Run and then
switched to Cloud Build to reduce GitHub Actions usage. It also masked test
failures, so it must not be restored unchanged.

Terraform and the old cloud setup/deploy scripts remain historical material.
This change does not inspect, stop, or delete any previously provisioned cloud
resources. Local commands do not call them.

Use the repository README and `run_api.py` for supported operation.
