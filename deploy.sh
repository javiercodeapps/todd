#!/bin/bash

# Deploy Todd Facturas
# Uso: ./deploy.sh "mensaje del commit"

set -e

COMMIT_MSG="${1:-Update}"
MODULE_NAME="${2:-todd_facturas}"

echo "Deploying..."

git add -A
git commit -m "$COMMIT_MSG"
git push

echo "Syncing oec..."
curl -s -X POST "https://api.oec.sh/api/public/v1/environments/892990aa-f261-4cc4-a2b8-85381250fbdd/quick-update" \
  -H "Authorization: Bearer oec_live_rw_JHaygVxgKzSXH4tLZn13VASrzWMfEbhlf_LwgMGQVTM" \
  -H "Content-Type: application/json" \
  -d '{"mode": "pull_restart"}'

echo ""
echo "Listo. Instalar con:"
echo "/opt/odoo19/venv/bin/python /opt/odoo19/odoo/odoo-bin -d todd -i $MODULE_NAME --stop-after-init"
