# Copia de seguridad fuera del servidor, en tu computador

Sin cuenta S3. El servidor genera cada día a las 3:15 a. m. una copia **cifrada** (`/var/backups/control/control-*.tar.gz.gpg`). Tu computador la trae con una llave SSH dedicada que **solo puede leer la última copia** (no entra al servidor, no ejecuta nada más). Aun si alguien robara esa llave o el archivo, sin `BACKUP_PASSPHRASE` no se puede abrir.

Esto cumple "una copia fuera del servidor" mientras tu computador esté encendido a la hora programada. Sigue siendo recomendable, con el tiempo, una segunda ubicación (otro VPS, una unidad de Google o un S3).

## 0. Probar que el servidor genera copias (en el servidor, como `control`)
```bash
cd /opt/control && ./deploy/backup.sh
ls -lh /var/backups/control
```
El script avisa que sin `BACKUP_S3_BUCKET` la copia queda solo en el servidor: es lo esperado. Debe aparecer un archivo `control-AAAAMMDD-HHMMSS.tar.gz.gpg`.

## 1. Crear la llave dedicada (en tu PC, PowerShell)
```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\respaldo_dh -N '""' -C "respaldo-pc"
Get-Content $HOME\.ssh\respaldo_dh.pub
```
Sin frase de contraseña a propósito: la tarea programada no puede escribirla. Por eso la restricción del paso 2 es obligatoria. Copia la línea pública (`ssh-ed25519 ... respaldo-pc`).

## 2. Autorizarla con restricción (en el servidor, como `control`)
Reemplaza `LLAVE_PUBLICA` por la línea completa que copiaste, **conservando** `restrict,command=...` delante:
```bash
cd /opt/control && git pull
chmod +x deploy/entregar_copia.sh
echo 'restrict,command="/opt/control/deploy/entregar_copia.sh" LLAVE_PUBLICA' >> ~/.ssh/authorized_keys
```

## 3. Probar desde el PC
```powershell
ssh -i $HOME\.ssh\respaldo_dh -o IdentitiesOnly=yes control@31.97.136.172 name
```
Debe imprimir el nombre de la última copia. Cualquier otra orden debe responder `Orden no permitida`, y no debe darte una terminal.

## 4. Traer la copia
Copia `deploy\windows\traer_copia.ps1` a tu PC (por ejemplo a `D:\Respaldos\`) y ejecútalo:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\Respaldos\traer_copia.ps1
```
Descarga a `D:\Respaldos\DH-Control`, verifica la huella SHA-256 y conserva las últimas 30. Si la huella no coincide, descarta el archivo.

## 5. Programarlo cada día
```powershell
schtasks /Create /SC DAILY /ST 08:30 /TN "DH Control - traer copia" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\Respaldos\traer_copia.ps1"
```
Cambia la hora a una en que tu PC esté encendido. Para quitarla: `schtasks /Delete /TN "DH Control - traer copia"`.

## 6. Restaurar (prueba mensual obligatoria)
1. Sube la copia al servidor (o a un servidor de prueba): `scp D:\Respaldos\DH-Control\control-....gpg control@IP:/var/backups/control/`.
2. En el servidor: `./deploy/restore.sh /var/backups/control/control-....gpg` (pide la `BACKUP_PASSPHRASE` guardada en tu gestor de contraseñas).
3. Ingresa a la aplicación y confirma que ves una carga reciente.

Si pierdes el servidor por completo: VPS nuevo → `bootstrap.sh` → clonar → crear `.env` (claves nuevas, **la misma `BACKUP_PASSPHRASE`**) → `restore.sh` con la copia de tu PC.
