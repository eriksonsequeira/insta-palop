#!/usr/bin/env bash
# Envia commits com sincronização e novas tentativas (várias tarefas gravam no repositório ao mesmo tempo).
set -e
for i in 1 2 3 4 5; do
  git pull -q --rebase && git push -q && exit 0
  echo "push falhou (tentativa $i); a tentar de novo"; sleep $((i * 4))
done
exit 1
