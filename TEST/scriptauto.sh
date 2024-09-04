#!/bin/bash

# Démarrer Xvfb
Xvfb :99 -screen 0 1024x768x16 &
XVFB_PID=$!

# Définir la variable d'affichage
export DISPLAY=:99

# Définir un gestionnaire pour tuer Xvfb quand le script se termine ou est interrompu
cleanup() {
  kill $XVFB_PID
}
trap cleanup EXIT

# Exécuter le script Python
python3 testrech_OK.py

# Tuer le processus Xvfb
kill $XVFB_PID
