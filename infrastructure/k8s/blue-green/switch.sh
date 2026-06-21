#!/bin/bash
# ─── Blue-Green Deployment Switch Script ──────────────────────────────────────
# Usage:
#   ./switch.sh green <new-image-tag>   # Deploy new version to green, switch traffic
#   ./switch.sh blue  <new-image-tag>   # Deploy new version to blue, switch traffic
#   ./rollback.sh                       # Rollback to previous slot

set -euo pipefail

NAMESPACE="copilot"
TARGET_SLOT="${1:-green}"
NEW_TAG="${2:-latest}"
REGISTRY="ghcr.io/your-org/ai-engineering-copilot-backend"

if [[ "$TARGET_SLOT" == "green" ]]; then
  INACTIVE_SLOT="blue"
else
  INACTIVE_SLOT="green"
fi

echo "🚀 Blue-Green Deploy: activating slot=$TARGET_SLOT tag=$NEW_TAG"

# Step 1: Update image on inactive slot
echo "📦 Step 1/5 — Updating $TARGET_SLOT deployment with tag $NEW_TAG"
kubectl set image deployment/copilot-backend-$TARGET_SLOT \
  backend=$REGISTRY:$NEW_TAG \
  -n $NAMESPACE

# Step 2: Scale up the new slot
echo "⬆️  Step 2/5 — Scaling up $TARGET_SLOT slot"
kubectl scale deployment/copilot-backend-$TARGET_SLOT --replicas=2 -n $NAMESPACE

# Step 3: Wait for rollout
echo "⏳ Step 3/5 — Waiting for $TARGET_SLOT rollout to complete..."
kubectl rollout status deployment/copilot-backend-$TARGET_SLOT -n $NAMESPACE --timeout=3m

# Step 4: Health check
echo "🔍 Step 4/5 — Health checking $TARGET_SLOT..."
POD=$(kubectl get pods -n $NAMESPACE -l "app=copilot-backend,slot=$TARGET_SLOT" \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [[ -z "$POD" ]]; then
  echo "❌ No pods found for slot $TARGET_SLOT. Aborting."
  exit 1
fi

HEALTH=$(kubectl exec -n $NAMESPACE $POD -- curl -sf http://localhost:8000/health 2>/dev/null || echo "fail")
if echo "$HEALTH" | grep -q "healthy"; then
  echo "✅ Health check passed"
else
  echo "❌ Health check failed. Aborting switch."
  kubectl scale deployment/copilot-backend-$TARGET_SLOT --replicas=0 -n $NAMESPACE
  exit 1
fi

# Step 5: Switch active service to new slot
echo "🔀 Step 5/5 — Switching traffic to $TARGET_SLOT"
kubectl patch service copilot-backend-active -n $NAMESPACE \
  -p "{\"spec\":{\"selector\":{\"slot\":\"$TARGET_SLOT\"}}}"
kubectl annotate service copilot-backend-active -n $NAMESPACE \
  "blue-green/active-slot=$TARGET_SLOT" --overwrite

# Scale down old slot after grace period
echo "⬇️  Scaling down $INACTIVE_SLOT slot in 60s..."
sleep 60
kubectl scale deployment/copilot-backend-$INACTIVE_SLOT --replicas=0 -n $NAMESPACE

echo ""
echo "✅ Blue-Green switch complete!"
echo "   Active slot : $TARGET_SLOT ($REGISTRY:$NEW_TAG)"
echo "   Standby slot: $INACTIVE_SLOT (scaled to 0)"
echo ""
echo "   Rollback:  kubectl patch service copilot-backend-active -n $NAMESPACE \\"
echo "              -p '{\"spec\":{\"selector\":{\"slot\":\"$INACTIVE_SLOT\"}}}'"
