#!/bin/bash
# Helper script to update kubeconfig for EKS cluster
# Usage: ./update_kubeconfig.sh <cluster-name> [region] [profile]

set -e

CLUSTER_NAME="${1:-abby-demo-cluster}"
REGION="${2:-eu-west-1}"
PROFILE="${3:-1sight}"

echo "Updating kubeconfig for EKS cluster: $CLUSTER_NAME in region $REGION"

# Update kubeconfig using AWS CLI
if [ -n "$PROFILE" ]; then
    aws eks update-kubeconfig \
        --name "$CLUSTER_NAME" \
        --region "$REGION" \
        --profile "$PROFILE"
else
    aws eks update-kubeconfig \
        --name "$CLUSTER_NAME" \
        --region "$REGION"
fi

echo ""
echo "Kubeconfig updated successfully!"
echo "Current context:"
kubectl config current-context
echo ""
echo "Testing cluster connectivity:"
kubectl cluster-info
