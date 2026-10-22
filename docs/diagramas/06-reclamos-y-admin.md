# Reclamos y resolución del admin (RQ10, RQ11)

Nuevo: el doc viejo solo mencionaba "resolver disputas" sin secuencia.

```mermaid
sequenceDiagram
    actor U as Usuario
    participant A as Aplicación
    participant S as Sistema
    participant BD as Base de datos
    actor D as Admin

    U->>A: Crear reclamo (partido, no-show o votación, motivo)
    A->>S: Registrar reclamo
    S->>BD: Verificar que el objetivo afecta al usuario
    alt Objetivo ajeno o inexistente
        S-->>A: Rechazar reclamo
        A-->>U: Mostrar error
    else Válido
        S->>BD: Guardar reclamo en estado abierto
        S->>BD: Crear notificación para el admin
        S-->>A: Reclamo registrado
        A-->>U: Mostrar confirmación
    end

    D->>A: Ver reclamos abiertos
    A->>S: Obtener reclamos
    S->>BD: Consultar reclamos abiertos
    BD-->>S: Reclamos
    S-->>A: Listado
    A-->>D: Mostrar reclamos

    alt Admin anula el no-show o la votación
        D->>A: Resolver reclamo como anulado
        A->>S: Registrar resolución
        S->>BD: Quitar no-show (sumar partido jugado) o eliminar votación
        S->>BD: Recalcular puntuación promedio del afectado
        S->>BD: Marcar reclamo resuelto
    else Admin rechaza el reclamo
        D->>A: Resolver reclamo como rechazado
        A->>S: Registrar resolución
        S->>BD: Marcar reclamo rechazado
    end
    S->>BD: Crear notificación para el autor del reclamo
    S-->>A: Resolución registrada
    A-->>D: Mostrar confirmación

    D->>A: Bloquear o desbloquear usuario
    A->>S: Registrar bloqueo
    S->>BD: Actualizar estado del usuario
    S-->>A: Usuario actualizado
    A-->>D: Mostrar confirmación
```
