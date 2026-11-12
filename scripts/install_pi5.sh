#!/usr/bin/env bash
# Instala o AcerteZero em uma Raspberry Pi 5 com Raspberry Pi OS.
# Execute como usuario comum: bash scripts/install_pi5.sh --led-count 31
set -euo pipefail

led_count=17
while (($#)); do
    case "$1" in
        --led-count)
            if (($# < 2)); then echo "Falta o numero de LEDs." >&2; exit 2; fi
            led_count=$2
            shift 2
            ;;
        -h|--help)
            echo "Uso: bash scripts/install_pi5.sh [--led-count N]"
            echo "Instala dependencias, libera SPI0 e habilita acertezero.service para o proximo boot."
            exit 0
            ;;
        *) echo "Opcao desconhecida: $1" >&2; exit 2 ;;
    esac
done
if [[ ! "$led_count" =~ ^[0-9]+$ ]] || ((led_count < 2)); then
    echo "--led-count deve ser um inteiro maior ou igual a 2." >&2
    exit 2
fi
if ((EUID == 0)); then
    echo "Execute como usuario comum, sem sudo; o script pedira sudo quando necessario." >&2
    exit 1
fi
if [[ "$(uname -s)" != Linux ]] || ! grep -aq 'Raspberry Pi 5' /proc/device-tree/model; then
    echo "Este instalador requer Raspberry Pi 5 com Raspberry Pi OS." >&2
    exit 1
fi
for command in apt-get python3 systemctl udevadm sudo; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Comando ausente: $command" >&2
        exit 1
    fi
done
boot_config=/boot/firmware/config.txt
if [[ ! -f "$boot_config" ]]; then
    echo "Nao encontrei $boot_config. Verifique se a Pi usa Raspberry Pi OS." >&2
    exit 1
fi

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$project_dir"
if [[ ! -f acertezero/piezo_game.py ]]; then
    echo "Execute o script dentro de uma copia completa do repositorio." >&2
    exit 1
fi
app_user=$(id -un)
venv_dir="$HOME/.venvs/acertezero"
service_file=/etc/systemd/system/acertezero.service

echo "Atualizando pacotes do Raspberry Pi OS (incluindo kernel/firmware quando disponiveis)..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-full python3-lgpio python3-dev build-essential

echo "Preparando ambiente Python: $venv_dir"
if [[ -f "$venv_dir/pyvenv.cfg" ]] && ! grep -qi '^include-system-site-packages = true$' "$venv_dir/pyvenv.cfg"; then
    echo "$venv_dir ja existe sem acesso ao python3-lgpio do sistema." >&2
    echo "Mova esse ambiente para outro nome e execute o instalador novamente." >&2
    exit 1
fi
python3 -m venv --system-site-packages "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install --upgrade \
    adafruit-blinka \
    adafruit-circuitpython-pixelbuf \
    Adafruit-Blinka-Raspberry-Pi5-Neopixel
"$venv_dir/bin/python" -c 'import board, digitalio, lgpio, adafruit_pixelbuf; from adafruit_raspberry_pi5_neopixel_write import neopixel_write; print("Importacoes Python: OK")'

echo "Configurando SPI0 para liberar GPIOs 7-11..."
sudo python3 - "$boot_config" <<'PY'
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime

config = Path(sys.argv[1])
original = config.read_text()
lines = original.splitlines(keepends=True)
new_lines = []
for line in lines:
    if re.match(r'^\s*#', line):
        new_lines.append(line)
    elif re.match(r'^\s*dtoverlay\s*=\s*spi0(?:[-,\s]|$)', line, re.IGNORECASE):
        new_lines.append('# AcerteZero desativou SPI0: ' + line)
    elif re.match(r'^\s*dtparam\s*=\s*spi\s*$', line, re.IGNORECASE):
        new_lines.append('dtparam=spi=off\n')
    elif re.match(r'^\s*dtparam\s*=', line, re.IGNORECASE):
        new_lines.append(re.sub(r'\b(spi\s*=\s*)on\b', r'\1off', line, flags=re.IGNORECASE))
    else:
        new_lines.append(line)
updated = ''.join(new_lines)
marker = '# AcerteZero: GPIOs 7-11 reservados para os alvos'
if marker not in updated:
    updated = updated.rstrip('\n') + '\n\n[all]\n' + marker + '\ndtparam=spi=off\n'
if updated != original:
    backup = config.with_name(config.name + '.acertezero-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.bak')
    shutil.copy2(config, backup)
    config.write_text(updated)
    print(f'Config alterada; backup: {backup}')
else:
    print('SPI0 ja estava configurado para o AcerteZero.')
PY

echo "Configurando permissao de acesso ao PIO para a fita WS2812B..."
if ! getent group gpio >/dev/null; then
    sudo groupadd --system gpio
fi
sudo usermod -aG gpio "$app_user"
pio_rule=/etc/udev/rules.d/70-acertezero-pio.rules
printf '%s\n' 'SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"' | sudo tee "$pio_rule" >/dev/null
sudo udevadm control --reload-rules

echo "Instalando servico systemd..."
# Um servico anterior pode estar usando os mesmos GPIOs durante a reinstalacao.
sudo systemctl stop acertezero.service 2>/dev/null || true
service_tmp=$(mktemp)
trap 'rm -f -- "$service_tmp"' EXIT
cat > "$service_tmp" <<EOF
[Unit]
Description=AcerteZero arena completa
After=local-fs.target systemd-udevd.service

[Service]
Type=simple
User=$app_user
WorkingDirectory=$project_dir
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/usr/bin/test -e /dev/pio0
ExecStart=$venv_dir/bin/python -m acertezero.piezo_game --arena-full --leds --led-count $led_count --judge-button
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 0644 "$service_tmp" "$service_file"
sudo systemctl daemon-reload
sudo systemctl enable acertezero.service

echo
echo "Instalacao concluida. Servico habilitado para iniciar sem login no proximo boot."
echo "Comando: $venv_dir/bin/python -m acertezero.piezo_game --arena-full --leds --led-count $led_count --judge-button"
if [[ ! -e /dev/pio0 ]]; then
    echo "ATENCAO: /dev/pio0 ainda nao existe. Reinicie apos a atualizacao do sistema e verifique novamente."
    echo "Se continuar ausente, nao havera controle da fita; confira kernel/firmware antes de usar a arena."
fi
echo "Confirme toda a fiacao da arena e reinicie: sudo reboot"
echo "Depois: systemctl status acertezero.service --no-pager"
echo "Logs: journalctl -u acertezero.service -b -f"
