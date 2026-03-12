## 🚀 FortiGate Backup Manager v1.9.5 — Backups vía CLI (SSH)

### ✅ Ahora con soporte de CLI mejorado
A petición del usuario, he migrado el motor de descarga de backups para usar la **FortiGate CLI** (vía SSH) como método primario cuando se usan credenciales (usuario/contraseña).

- **Por qué el cambio:** La API REST de FortiGate puede ser muy caprichosa con los permisos, versiones de firmware (7.4+) y VDOMs. La CLI es el método más directo y compatible.
- **Cómo funciona:** El programa ahora intenta conectarse vía SSH al puerto 22, ejecuta `show full-configuration` y captura el resultado.
- **Fallback Automático:** Si el equipo no tiene SSH habilitado o la conexión falla, el programa automáticamente intentará el método de API REST (el anterior) para no dejarte sin backup.

### 🔧 Otras mejoras
- **Detección de VDOMs:** Se corrigieron errores 424 que ocurrían en equipos sin VDOMs habilitados.
- **Port Suggestion:** Si un equipo da timeout en 10443, el mensaje ahora sugiere revisar si el puerto correcto es 443.

---
**Nota:** Esta versión requiere que el equipo tenga habilitado el acceso SSH (usualmente puerto 22) para usar el nuevo método de CLI.
