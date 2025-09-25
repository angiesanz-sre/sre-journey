# W04 Midpoint — Bash + cron + debug

Esta carpeta contiene:
- `scripts/log_rotator.sh` — rotación de logs (gzip) y retención
- `scripts/backup.sh` — backup sencillo con retención 7 días
- `scripts/healthcheck.sh` — checks básicos con salida ≠0 en fallo
- `Makefile` — tareas rápidas: `make setup`, `make test-rotate`, `make backup`, `make health`

## Uso rápido (modo práctica, sin tocar /var/log)
```bash
make setup
make test-rotate   # crea logs de prueba y rota (retiene 3)
make backup        # genera tar.gz en ./backups
make health        # ejecuta checks (ajusta a tu máquina)
```

## Cron (cuando ya lo tengas adaptado)
Edita rutas absolutas y añade con `crontab -e`:
```
*/15 * * * * /usr/local/bin/healthcheck.sh >> /var/log/healthcheck.log 2>&1
0 0 * * * /usr/local/bin/log_rotator.sh "/var/log/*.log" 5
```
