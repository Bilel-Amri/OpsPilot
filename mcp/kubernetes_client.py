"""Kubernetes API client configuration for OpsPilot MCP."""

from __future__ import annotations

import os

from kubernetes import client, config


def get_core_v1_api() -> client.CoreV1Api:
    """
    Create a Kubernetes Core API client.

    Local development:
        Authenticate using the user's kubeconfig.

    Inside Kubernetes:
        Authenticate using the Pod's ServiceAccount.
    """

    if os.getenv("KUBERNETES_SERVICE_HOST"):
        # Running inside a Kubernetes Pod.
        config.load_incluster_config()
    else:
        # Running locally during development.
        config.load_kube_config()

    return client.CoreV1Api()