# Recursos

No se usa ningún recurso externo. Todo se genera por código en tiempo de ejecución:

| Recurso | Dónde se genera |
|---|---|
| Luchadores y animaciones | `src/ui/fighter_renderer.py` (poses por articulaciones dibujadas con pygame) |
| Fondo de la arena | `src/game/arena.py` |
| Efectos de impacto | `src/ui/effects.py` |
| Sonidos | `src/ui/sound.py` (síntesis con NumPy) |
| Fuentes | fuentes del sistema (Impact / Arial / Segoe UI), con la fuente por defecto de pygame como respaldo |

Única excepción: `logo/netsu_games.png`, logo de **Netsu Games** aportado por el autor del proyecto
(PNG con transparencia, solo recortado). Se muestra 2 s al iniciar (`Game._draw_splash`).

Por eso no hay licencias de terceros que cumplir. Si en el futuro se añaden spritesheets o sonidos,
colóquelos en `sprites/`, `backgrounds/`, `sounds/` y `fonts/` y documente aquí su origen y licencia.
