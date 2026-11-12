from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from mcp.server.fastmcp import FastMCP

NAMESPACE = "opspilot-lab"

mcp = FastMCP(
    "OpsPilot Kubernetes MCP",
    host="0.0.0.0",
    port=8001,
    streamable_http_path="/mcp",
)

def get_kubernetes_core_api():
    """Initialise le client Kubernetes."""
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()

    return client.CoreV1Api()


@mcp.tool()
def list_pods() -> list[dict]:
    """Liste les Pods du namespace opspilot-lab."""
    v1 = get_kubernetes_core_api()
    pods = v1.list_namespaced_pod(namespace=NAMESPACE)

    return [
        {
            "name": pod.metadata.name,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "namespace": NAMESPACE,
        }
        for pod in pods.items
    ]


@mcp.tool()
def get_pod_status(pod_name: str) -> dict:
    """Retourne le statut détaillé d'un Pod."""
    v1 = get_kubernetes_core_api()
    pod = v1.read_namespaced_pod(
        name=pod_name,
        namespace=NAMESPACE,
    )

    return {
        "name": pod.metadata.name,
        "phase": pod.status.phase,
        "node": pod.spec.node_name,
        "pod_ip": pod.status.pod_ip,
        "conditions": [
            {
                "type": condition.type,
                "status": condition.status,
                "reason": condition.reason,
            }
            for condition in (pod.status.conditions or [])
        ],
        "containers": [
            {
                "name": container.name,
                "ready": container.ready,
                "restart_count": container.restart_count,
                "state": (
                    container.state.waiting.reason
                    if container.state and container.state.waiting
                    else "Running"
                    if container.state and container.state.running
                    else "Terminated"
                    if container.state and container.state.terminated
                    else "Unknown"
                ),
            }
            for container in (pod.status.container_statuses or [])
        ],
    }


@mcp.tool()
def get_pod_logs(pod_name: str, tail_lines: int = 100) -> str:
    """Lit les dernières lignes des logs d'un Pod."""
    v1 = get_kubernetes_core_api()

    return v1.read_namespaced_pod_log(
        name=pod_name,
        namespace=NAMESPACE,
        tail_lines=max(1, min(tail_lines, 500)),
    )


@mcp.tool()
def get_recent_events() -> list[dict]:
    """Retourne les événements récents du namespace."""
    v1 = get_kubernetes_core_api()
    events = v1.list_namespaced_event(namespace=NAMESPACE)

    return [
        {
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
            "object": event.involved_object.name,
            "count": event.count,
            "last_timestamp": str(
                event.last_timestamp or event.event_time or ""
            ),
        }
        for event in events.items
    ]

@mcp.tool()
def detect_pod_issues() -> list[dict]:
    """Détecte les problèmes actifs des Pods et conteneurs."""
    v1 = get_kubernetes_core_api()
    pods = v1.list_namespaced_pod(namespace=NAMESPACE)

    issues = []

    for pod in pods.items:
        pod_name = pod.metadata.name

        # Détecter les problèmes de statut du Pod
        if pod.status.phase in ["Pending", "Failed", "Unknown"]:
            issues.append({
                "pod": pod_name,
                "type": "PodStatus",
                "problem": pod.status.phase,
            })

        # Vérifier les conteneurs
        for container in (pod.status.container_statuses or []):
            state = container.state

            # Détecter les erreurs actives
            if state and state.waiting:
                reason = state.waiting.reason

                if reason in [
                    "CrashLoopBackOff",
                    "ImagePullBackOff",
                    "ErrImagePull",
                    "CreateContainerConfigError",
                ]:
                    issues.append({
                        "pod": pod_name,
                        "container": container.name,
                        "type": "ContainerError",
                        "problem": reason,
                    })

            # Détecter les conteneurs non prêts
            if not container.ready:
                issues.append({
                    "pod": pod_name,
                    "container": container.name,
                    "type": "ContainerNotReady",
                    "restart_count": container.restart_count,
                })

    return issues

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
