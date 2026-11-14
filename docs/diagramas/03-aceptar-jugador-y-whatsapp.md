# Aceptar jugador y compartir WhatsApp (RQ6)

```mermaid
sequenceDiagram
    actor O as Organizador
    participant A as Aplicación
    participant S as Sistema
    participant BD as Base de datos
    actor J as Jugador aceptado

    O->>A: Ver lista de espera
    A->>S: Obtener postulaciones
    S->>BD: Obtener postulaciones en espera con perfiles
    BD-->>S: Postulaciones
    S-->>A: Lista ordenada por puntuación (sin puntuación al final, desempate por llegada)
    A-->>O: Mostrar lista de espera

    Note over O,J: Aceptar y rechazar, solo antes del inicio del partido. Si ya empezó, responde "El partido ya empezó" (409)
    O->>A: Aceptar jugador
    A->>S: Registrar aceptación
    S->>BD: Marcar postulación aceptada y restar un cupo
    S->>BD: Crear notificación para el jugador (sin el WhatsApp)
    opt Cupos faltantes llegan a 0
        S->>BD: Marcar partido completo
        S->>BD: Rechazar postulaciones en espera
        S->>BD: Crear notificación de partido completo para cada rechazado
    end
    S-->>A: Aceptación registrada con WhatsApp del jugador
    A-->>O: Mostrar WhatsApp del jugador
    S--)J: Notificar aceptación (el aviso dice dónde ver el WhatsApp, no lo incluye)

    J->>A: Ver mis postulaciones
    A->>S: Obtener postulaciones del jugador
    S->>BD: Obtener postulaciones con su partido y su organizador
    BD-->>S: Postulaciones
    S-->>A: Postulación aceptada con WhatsApp del organizador
    A-->>J: Mostrar WhatsApp del organizador
    Note over O,J: Cada uno ve el WhatsApp del otro mientras la postulación está aceptada y el partido no se canceló

    O->>A: Rechazar postulación
    A->>S: Registrar rechazo
    S->>BD: Marcar postulación rechazada
    S->>BD: Crear notificación para el jugador
```
