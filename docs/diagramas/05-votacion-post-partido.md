# Votación después del partido (RQ8)

Cambios contra el doc viejo: deuda cuenta por partido, solo el organizador marca no-show, sin cancha como entidad (se vota al complejo), sin ventana de votación.

```mermaid
sequenceDiagram
    participant S as Sistema
    participant BD as Base de datos
    participant A as Aplicación
    actor P as Participante
    actor O as Organizador

    Note over S: Pasa la fecha y hora del partido
    S->>BD: Marcar partido jugado y sumar un partido jugado a cada participante
    S->>BD: Crear votaciones pendientes (cada participante a los demás participantes y al complejo)
    S->>BD: Crear notificación de votaciones pendientes

    P->>A: Ver votaciones pendientes
    A->>S: Obtener votaciones pendientes
    S->>BD: Consultar votaciones pendientes del participante
    BD-->>S: Jugadores y complejo a puntuar
    S-->>A: Votaciones pendientes
    A-->>P: Mostrar jugadores y complejo

    loop Por cada votación pendiente
        P->>A: Asignar de 0 a 5 estrellas
        A->>S: Registrar votación
        S->>BD: Marcar votación emitida
        S->>BD: Recalcular puntuación promedio del receptor
    end

    opt Organizador marca un aceptado ausente
        O->>A: Marcar no-show
        A->>S: Registrar no-show
        S->>BD: Marcar no-show en el aceptado
        S->>BD: Restar un partido jugado y recalcular puntuación del ausente
        S->>BD: Eliminar votaciones pendientes del ausente
    end

    S->>BD: Contar partidos con votaciones pendientes del participante
    BD-->>S: Deuda
    S-->>A: Estado de habilitación
    A-->>P: Mostrar si quedó habilitado para publicar y postularse

```
