#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CLUSTER="opspilot"
NAMESPACE="opspilot-lab"
MONITORING_NAMESPACE="monitoring"

echo "======================================"
echo "       Démarrage de OpsPilot"
echo "======================================"

# 1. Vérifier les outils nécessaires
for cmd in docker kind kubectl helm node npm; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERREUR : $cmd n'est pas installé."
        exit 1
    fi
done

docker info >/dev/null 2>&1 || {
    echo "ERREUR : Docker n'est pas démarré ou inaccessible."
    exit 1
}

# 2. Créer le cluster Kind s'il n'existe pas
if ! kind get clusters | grep -qx "$CLUSTER"; then
    echo "[1/9] Création du cluster Kind..."
    kind create cluster --config k8s/kind-config.yaml
else
    echo "[1/9] Cluster Kind déjà présent."
fi

kubectl wait --for=condition=Ready nodes --all --timeout=180s

# 3. Construire les images Docker
echo "[2/9] Construction des images Docker..."

docker build -f backend/Dockerfile -t opspilot-api:1.0.0 .
docker build -f mcp/Dockerfile -t opspilot-mcp:0.3.0 .
docker build -t dar-immo:1.0 ./dar-immo

# 4. Charger les images dans Kind
echo "[3/9] Chargement des images dans Kind..."

docker pull postgres:17

kind load docker-image \
    opspilot-api:1.0.0 \
    opspilot-mcp:0.3.0 \
    dar-immo:1.0 \
    postgres:17 \
    --name "$CLUSTER"

# 5. Créer le namespace et configurer RBAC
echo "[4/9] Configuration Kubernetes..."

kubectl apply -f k8s/rbac/

# 6. Déployer PostgreSQL et Dar-Immo
echo "[5/9] Déploiement PostgreSQL et Dar-Immo..."

kubectl apply -f k8s/dar-immo/postgres/

kubectl rollout status deployment/postgres \
    -n "$NAMESPACE" --timeout=180s

kubectl apply -f k8s/dar-immo/app/

kubectl rollout status deployment/dar-immo-app \
    -n "$NAMESPACE" --timeout=180s

# 7. Déployer MCP et Backend
echo "[6/9] Déploiement MCP et API..."

kubectl apply -f k8s/mcp/
kubectl rollout status deployment/opspilot-mcp \
    -n "$NAMESPACE" --timeout=180s

kubectl apply -f k8s/backend/
kubectl rollout status deployment/opspilot-api \
    -n "$NAMESPACE" --timeout=180s

# 8. Installer le monitoring avec la version existante
echo "[7/9] Installation du monitoring..."

helm repo add prometheus-community \
    https://prometheus-community.github.io/helm-charts \
    --force-update

helm repo update

helm upgrade --install opspilot-monitoring \
    prometheus-community/kube-prometheus-stack \
    --version 93.2.2 \
    --namespace "$MONITORING_NAMESPACE" \
    --create-namespace \
    --values k8s/monitoring/values.yaml \
    --wait --timeout 10m

kubectl apply -f k8s/monitoring/opspilot-dashboard.yaml

# 9. Démarrer les accès locaux
echo "[8/9] Préparation du frontend..."

if [ ! -d frontend/node_modules ]; then
    (cd frontend && npm ci)
fi

start_background() {
    local name="$1"
    local port="$2"
    shift 2

    if ss -ltn | grep -qE "[:.]${port}[[:space:]]"; then
        echo "$name : port $port déjà utilisé, démarrage ignoré."
        return
    fi

    local pid_file="/tmp/opspilot-${name}.pid"
    local log_file="/tmp/opspilot-${name}.log"

    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "$name est déjà démarré."
        return
    fi

    nohup "$@" >"$log_file" 2>&1 &
    echo "$!" > "$pid_file"
    sleep 2

    if ! kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "ERREUR : impossible de démarrer $name."
        cat "$log_file"
        exit 1
    fi

    echo "$name démarré."
}

start_background api 18000 \
    kubectl port-forward --address 127.0.0.1 \
    -n "$NAMESPACE" service/opspilot-api 18000:8000

start_background grafana 3000 \
    kubectl port-forward --address 127.0.0.1 \
    -n "$MONITORING_NAMESPACE" service/opspilot-monitoring-grafana 3000:80

start_background frontend 5173 \
    bash -c "cd '$ROOT_DIR/frontend' && exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo "[9/9] Vérification finale..."
sleep 3

echo
echo "======================================"
echo "       OpsPilot est démarré !"
echo "======================================"
echo "Frontend : http://localhost:5173"
echo "API      : http://localhost:18000/health"
echo "Grafana  : http://localhost:3000"
echo
echo "Pods Kubernetes :"
kubectl get pods -n "$NAMESPACE"
echo
echo "Monitoring :"
kubectl get pods -n "$MONITORING_NAMESPACE"
echo
echo "Logs : /tmp/opspilot-*.log"
