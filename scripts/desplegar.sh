#!/usr/bin/env bash
# Actualiza la app en el servidor con la rama main de este repo
#   scripts/desplegar.sh            copia main a la Pi, instala dependencias y reinicia el servicio
#   SERVIDOR=otro scripts/desplegar.sh   usa otro host de ~/.ssh/config (por defecto, server)
# Copia una clonación limpia de main, así no viajan .venv, .env, worktrees ni cambios sin commit
set -euo pipefail

SERVIDOR="${SERVIDOR:-server}"
DESTINO="/home/pi/agrocebada"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone -q --branch main "$RAIZ" "$TMP/agrocebada"
git -C "$TMP/agrocebada" remote set-url origin https://github.com/alan-pv/AgroCebada_Hackaton.git
echo "Desplegando $(git -C "$TMP/agrocebada" log --oneline -1)"

rsync -az --delete --exclude .venv --exclude .env "$TMP/agrocebada/" "$SERVIDOR:$DESTINO/"
ssh "$SERVIDOR" "cd $DESTINO && ~/.local/bin/uv run app install && sudo systemctl restart agrocebada"

# El servicio tarda unos segundos en cargar datos y modelo
for _ in $(seq 60); do
  if ssh "$SERVIDOR" "curl -sf localhost:8090/health" >/dev/null; then
    echo "Listo: https://agrocebada.alan-pv.com"
    exit 0
  fi
  sleep 1
done
echo "El servicio no respondió en 60 s. Revisa: ssh $SERVIDOR journalctl -u agrocebada -n 30" >&2
exit 1
