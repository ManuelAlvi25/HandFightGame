# Gesture Fighter

Juego de peleas 2D (vista lateral) contra una IA, controlado con **gestos de la mano** captados por la
cámara web (MediaPipe Hands) y preparado para un **Arduino con Wi-Fi**, sensor ultrasónico y LEDs.
Mientras no haya hardware, todo funciona en **modo simulación**.

- Puño cerrado → **atacar** · Palma abierta → **defender** · Sin mano → postura neutral segura
- Movimiento lateral con sensor ultrasónico (simulado), posición de la mano o teclado
- IA con máquina de estados y 3 dificultades · LEDs de vida simulados en pantalla
- Gráficos y sonidos generados por código (sin recursos externos, ver `assets/README.md`)

---

## 1. Instalación (Windows)

Requisito: **Python 3.11 de 64 bits** (probado con 3.11.9). MediaPipe 0.10.21 no tiene versión para
Python 3.13/3.14, por eso se usa 3.11.

La forma fácil: **doble clic en `run.bat`**. La primera vez crea `.venv` e instala las dependencias.

Manual:

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python main.py
```

Dependencias (`requirements.txt`) y por qué esas versiones:

| Paquete | Versión | Nota |
|---|---|---|
| mediapipe | 0.10.21 | última con la API `solutions.hands` (no requiere descargar modelos `.task`) |
| numpy | <2 | exigido por mediapipe 0.10.21 |
| opencv-contrib-python | 4.11 (lo instala mediapipe) | **no** instalar además `opencv-python`: ambos traen `cv2` y chocan |
| pygame | 2.6 | motor del juego |
| pyserial | 3.5 | solo para conectar Arduino por USB |
| pytest | 9 | pruebas |

## 2. Ejecución

```bash
run.bat
```

Opciones (también valen con `run.bat`):

| Opción | Efecto |
|---|---|
| `--no-camera` | sin cámara, solo teclado |
| `--difficulty facil\|normal\|dificil` | dificultad inicial |
| `--demo` | el jugador también lo maneja la IA (ver a los personajes combatir). `F2` lo alterna en partida |
| `--auto` | salta los menús y encadena combates |
| `--hardware` / `--simulation` | fuerza el modo de hardware sin editar la config |
| `--debug` | registro detallado (también en `logs/game.log`) |

## 3. Controles

| Acción | Gesto (cámara) | Teclado |
|---|---|---|
| Atacar (puñetazo) | Puño cerrado | `J` o `Espacio` |
| Defender | Palma abierta (mantener) | `K` (mantener) |
| Golpe fuerte | (gesto "dos puños", desactivado por defecto) | `L` |
| Mover | Sensor ultrasónico / mano / teclado | `A` `D` o `←` `→` |
| Pausa | | `P` o `Esc` |
| Mostrar/ocultar cámara | | `C` |
| Cambiar fuente de movimiento | | `M` (sensor → mano → teclado) |
| Modo demo | | `F2` |

Menús: `←/→` luchador, `↑/↓` dificultad, `Enter` combatir. Tras el combate: `R` revancha, `Q` selección.

## 4. Cómo probar cada gesto

1. Ejecute el juego y entre en combate. El **panel de cámara** (arriba a la derecha) muestra la imagen
   en espejo con los puntos de la mano, el gesto detectado y su confianza. El **panel inferior
   izquierdo** muestra el gesto, la barra de confianza, el número de manos y la acción activa.
2. Use **buena iluminación** y coloque la mano a 40–80 cm de la cámara, palma hacia la cámara.
3. **Palma abierta**: extienda los cinco dedos. Tras ~3 frames aparece "PALMA ABIERTA", la acción `block`
   y el luchador levanta la guardia con un escudo azul. Mientras la mantenga, se defiende (recibe 20 % del daño).
4. **Puño cerrado**: cierre la mano. Se dispara **un** ataque. Mantener el puño **no** repite el ataque;
   para volver a golpear abra la mano y ciérrela otra vez (hay 300 ms de recuperación entre ataques).
5. **Sin mano**: retire la mano del encuadre → "SIN MANO", el luchador vuelve a neutral.
6. Mano a medio cerrar: no debería activar nada (tolerancia + histéresis evitan parpadeos).

## 5. Calibrar los gestos (`config/gesture_config.json`)

En la parte inferior de la imagen de la cámara aparecen los valores crudos de la mano:
`T` pulgar, `I` índice, `M` medio, `R` anular, `P` meñique. Para los cuatro dedos largos es
*distancia(punta, muñeca) / distancia(nudillo, muñeca)*: ~0.9–1.2 con el dedo doblado y ~1.8–2.1 extendido.

| Parámetro | Significado |
|---|---|
| `features.curled_ratio` / `extended_ratio` | ratio a partir del cual un dedo cuenta 0 % / 100 % extendido (entre medias, proporcional = tolerancia) |
| `features.thumb_curled` / `thumb_extended` | igual para el pulgar |
| `confidence_threshold` | confianza para **activar** el gesto |
| `release_threshold` | confianza por debajo de la cual se **desactiva** (histéresis) |
| `min_frames`, `min_time_ms` | confirmación temporal antes de activar |
| `release_frames` (global) | frames por debajo de `release_threshold` para soltar |
| `cooldown_ms` | recuperación mínima entre disparos |
| `priority` | si hay varios gestos activos gana el de mayor prioridad |
| `mode` | `trigger` (una vez por activación) o `hold` (mientras se mantenga) |
| `hands` | `any`, `both`, `left`, `right` |
| `params` | parámetros propios del detector (p. ej. `thumb_weight`) |

Si el puño no se reconoce, suba `curled_ratio` (p. ej. 1.25). Si la palma tarda en reconocerse, baje
`extended_ratio` (p. ej. 1.6).

## 6. Añadir un gesto nuevo (sin tocar el combate)

1. **Si la forma ya existe** (`fist`, `open_palm`, `index_point`): basta con añadir una entrada en
   `gesture_config.json`. Ejemplo incluido: `two_fists` (dos puños → `heavy_attack`); ponga `"enabled": true`.
2. **Forma nueva**: registre un detector en `src/vision/gesture_recognizer.py`:
   ```python
   @register_detector("pinch")
   def pinch(f, params):            # f.extension["index"] etc. en 0..1
       return f.extension["index"] * (1 - f.extension["middle"])
   ```
3. **Acción nueva**: regístrela en `src/game/actions.py` y, si es un golpe, añada su movimiento en
   `game_config.json → moves`:
   ```python
   @register_action("special", "trigger")
   def _special(character, active):
       character.request_attack("special")
   ```
El controlador de combate (`combat.py`, `character.py`) no cambia: solo recibe nombres de acción.
`tests/test_extensibility.py` demuestra el proceso completo.

## 7. Movimiento lateral y simulación del sensor

`config/hardware_config.json → ultrasonic`:

| Clave | Uso |
|---|---|
| `min_cm`, `max_cm` | rango útil: `min_cm` = extremo izquierdo de la arena, `max_cm` = extremo derecho |
| `invert` | invierte el sentido |
| `valid_min_cm`, `valid_max_cm` | lecturas fuera de este rango se descartan como inválidas |
| `median_window` | filtro de mediana (anti-ruido) |
| `max_jump_cm` | descarta picos aislados (se aceptan si se repiten 3 veces) |
| `timeout_s` | sin lecturas válidas durante este tiempo → sin datos |

`game_config.json → movement`: `source` inicial, `smoothing` (1 = sin suavizado), `deadzone`
(fracción del recorrido que se ignora como temblor), `hand_x_range` (zona de la imagen usada para la mano).

**Probar en simulación**: en combate, con la fuente "SENSOR ULTRASÓNICO", mueva la distancia simulada
con `A`/`D` (o `←`/`→`) o **arrastrando el deslizador** del panel inferior derecho. El jugador se desplaza
a la posición equivalente, suavizado. Pulse `M` para cambiar a "POSICIÓN DE LA MANO" (mover la mano de
izquierda a derecha frente a la cámara) o a "TECLADO". Si la fuente activa no da datos, `A`/`D` mueven
directamente al luchador.

## 8. LEDs de vida (simulados)

El panel inferior central muestra 5 LEDs por luchador: se apagan progresivamente con la vida (siempre
queda uno mientras haya vida) y **parpadean** con aviso "¡CRÍTICO!" al 25 % o menos. Configurable en
`hardware_config.json → leds` (`player_count`, `enemy_count`, `critical_threshold`, `blink_hz`).
La misma trama se envía al Arduino (`LED:...`) en modo hardware.

## 9. Arquitectura

```
main.py                     argumentos, carga de config
config/                     game_config / gesture_config / hardware_config (JSON)
src/game/                   lógica pura (sin pygame salvo arena.py y game.py)
  character.py              estados, ataques por fases (startup/active/recovery), bloqueo, aturdimiento
  combat.py                 alcance, golpes, separación, temporizador y victoria
  ai.py                     IA: IDLE, APPROACH, ATTACK, DEFEND, RECOVER, RETREAT, VICTORY, DEFEAT
  actions.py                registro nombre-de-acción → orden al personaje
  player.py / enemy.py      luchador humano / luchador IA
  arena.py / game.py        fondo, escenas y bucle principal
src/vision/                 hilo de visión desacoplado del juego
  camera.py                 captura OpenCV (DirectShow en Windows)
  hand_tracker.py           MediaPipe Hands → landmarks, centro, tamaño
  gesture_recognizer.py     características de los dedos + registro de detectores
  gesture_manager.py        confirmación temporal, histéresis, prioridad, cooldown
  vision_service.py         hilo: cámara → MediaPipe → gestos; reintenta si falla
src/controls/               input_manager.py (teclado+gestos), movement_controller.py (fuentes de movimiento)
src/hardware/               capa de abstracción de hardware
  hardware_interface.py     interfaces: DistanceSensor, LedOutput, HealthOutput, ConnectionMonitor
  hardware_simulator.py     modo simulación
  arduino_wifi.py           modo hardware: TCP (Wi-Fi) o serie, en hilo propio con reconexión
  protocol.py               protocolo de texto con checksum
  ultrasonic_sensor.py      validación y filtrado de distancias
  led_controller.py         vida → LEDs, parpadeo crítico
src/ui/                     hud, menús, panel de cámara, efectos, dibujo de luchadores, sonido
arduino/firmware_example/   esqueleto de firmware
tests/                      pytest
```

Rendimiento: la cámara y MediaPipe corren en otro hilo; el juego solo lee el último resultado, así que
mantiene 60 FPS aunque la cámara vaya más lenta. MediaPipe procesa ~58 imágenes/s en la laptop de
prueba; la cámara de esa laptop entrega 9 fps con poca luz (exposición larga), por eso conviene
iluminar bien la mano.

Errores manejados: cámara ausente o desconectada (reintento cada 3 s), fallo de MediaPipe (se
reinicia), configuración de gestos inválida (juego sigue con teclado), Arduino inalcanzable o mudo
(reintento cada 2 s, estado visible en el HUD), lecturas de distancia inválidas (descartadas),
sin audio (juego en silencio).

## 10. Conectar el Arduino (cuando tenga el hardware)

> El código de comunicación está probado contra un Arduino **simulado** en memoria
> (`tests/test_hardware.py`). **No se ha probado con hardware físico** y el firmware no se ha compilado
> (no había Arduino IDE/arduino-cli en el equipo de desarrollo).

### Componentes necesarios

| Cantidad | Componente |
|---|---|
| 1 | Placa con Wi-Fi: **ESP32 DevKit** (recomendada, barata), Arduino UNO R4 WiFi o Nano 33 IoT |
| 1 | Sensor ultrasónico HC-SR04 (o HC-SR04P, que funciona a 3.3 V) |
| 10 | LEDs (5 verdes jugador, 5 rojos enemigo) |
| 10 | Resistencias 220–330 Ω para los LEDs |
| 2 | Resistencias 1 kΩ y 2 kΩ (divisor para ECHO si la placa es de 3.3 V, p. ej. ESP32) |
| 1 | Protoboard + cables dupont |
| 1 | Cable USB de datos (programar y, opcionalmente, alimentar) |

### Conexiones (pines por defecto del firmware)

| Señal | ESP32 | UNO R4 WiFi / Nano 33 IoT |
|---|---|---|
| HC-SR04 VCC / GND | 5V (VIN) / GND | 5V / GND |
| HC-SR04 TRIG | GPIO 5 | D9 |
| HC-SR04 ECHO | GPIO 18 **a través del divisor 1k/2k** | D10 (UNO R4 tolera 5 V; Nano 33 IoT es de 3.3 V: usar divisor) |
| LEDs jugador (ánodo → resistencia → pin, cátodo a GND) | 13, 12, 14, 27, 26 | D2–D6 |
| LEDs enemigo | 25, 33, 32, 15, 4 | D7, D8, D11, D12, D13 |

### Pasos

1. Abra `arduino/firmware_example/firmware_example.ino` en el Arduino IDE, instale el soporte de la
   placa (ESP32: gestor de tarjetas "esp32 by Espressif") y ajuste pines/SSID si hace falta.
2. Súbalo. Por defecto la placa crea la red Wi-Fi **GestureFighter** (clave `pelea1234`) con IP `192.168.4.1`.
   (Con `WIFI_AP_MODE 0` se une a su router y muestra su IP por el Monitor Serie.)
3. Conecte la laptop a esa red y edite `config/hardware_config.json`:
   `"mode": "hardware"`, `"transport": "tcp"`, `"tcp": {"host": "192.168.4.1", "port": 5000}`.
   Por USB en vez de Wi-Fi: `"transport": "serial"`, `"serial": {"port": "COM3"}` (vea el puerto en el
   Administrador de dispositivos) y compile el firmware para una placa sin Wi-Fi o adapte `USE_SERIAL_ONLY`.
4. Ejecute el juego. El HUD muestra `Arduino: WIFI 192.168.4.1:5000 [conectado]` y la distancia real.
5. Calibre `ultrasonic.min_cm` / `max_cm` según dónde se colocará el jugador.

### Protocolo

Líneas de texto ASCII terminadas en `\n`, iguales por TCP o serie: `COMANDO[:arg1,arg2]*XX`, donde `XX` es el
XOR en hexadecimal de los bytes anteriores a `*` (desactivable con `protocol.checksum: false`).

| Dirección | Mensaje | Significado |
|---|---|---|
| Arduino → PC | `HELLO:ESP32,5,5` | placa y número de LEDs, al conectar |
| Arduino → PC | `D:23.4` | distancia en cm (cada 60 ms) |
| Arduino → PC | `PONG` | respuesta a `PING` |
| Arduino → PC | `ERR:CHK` | error de checksum / comando |
| PC → Arduino | `PING` | cada `ping_interval` s; sin respuesta en `timeout` s → error y reconexión |
| PC → Arduino | `HP:75,40` | vida jugador / enemigo en % (solo al cambiar) |
| PC → Arduino | `LED:11100,11111,01` | estado de cada LED y flags de vida crítica (solo al cambiar) |

Opciones compatibles: TCP sobre Wi-Fi (ESP32, UNO R4 WiFi, Nano 33 IoT, MKR WiFi 1010, Pico W con
adaptación) o USB serie (cualquier Arduino). Para usar HTTP o WebSocket basta con otra clase `Transport`
en `arduino_wifi.py`; el resto del juego no cambia.

## 11. Pruebas

```bash
.venv\Scripts\python -m pytest -v
```

Resultado en la máquina de desarrollo (Windows 11, Python 3.11.9): **62 pruebas superadas, 0 fallos**.

| Archivo | Qué cubre |
|---|---|
| `test_gestures.py` | reconocimiento de puño/palma con manos sintéticas, mano a medias ignorada, confirmación por frames, un ataque por puño, re-ataque al reabrir, cooldown, histéresis, defensa mantenida/soltada, neutral sin mano, validación de config |
| `test_extensibility.py` | registrar detector + gesto + acción nuevos, gesto a dos manos con prioridad, ids duplicados |
| `test_combat.py` | daño en alcance, fallo fuera de alcance o de espaldas, bloqueo, aturdimiento y recuperación, cooldown, K.O., vida nunca negativa, reinicio de vida, tiempo agotado, separación y orientación, transiciones ataque/defensa/neutral |
| `test_ai.py` | aproximación, ataque, bloqueo reactivo, sin bloqueo con probabilidad 0, victoria/derrota, difícil más agresiva que fácil, la IA fácil se puede vencer |
| `test_movement.py` | distancia→posición, límites, inversión, suavizado, zona muerta, fuentes intercambiables, lecturas inválidas (None, NaN, negativas, texto…), mediana, picos, timeout |
| `test_leds.py` | apagado progresivo, distinto número de LEDs, parpadeo crítico |
| `test_hardware.py` | protocolo y checksum, buffer de líneas, simulador, fábrica de modos, enlace con Arduino simulado: conexión, distancia, envío de vida/LEDs, mensajes corruptos, pérdida de conexión y reconexión, fallo al conectar, TCP real inalcanzable |
| `test_game_smoke.py` | el juego completo corre sin ventana en modo demo; el sensor simulado mueve al jugador |

Además se verificó a mano: el juego renderiza menús, combate y resultados (capturas en modo sin ventana),
la cámara real de la laptop se abre y MediaPipe procesa imágenes dentro del juego, y el juego mantiene
60 FPS con la cámara activa. **No** se pudo comprobar el reconocimiento con una mano real frente a la
cámara durante el desarrollo; los umbrales por defecto pueden necesitar ajuste (sección 5).

## 12. Pendiente exclusivamente por falta de hardware

- Compilar y subir el firmware a la placa elegida; ajustar pines.
- Probar la conexión real por Wi-Fi/serie y medir latencia.
- Calibrar `min_cm`/`max_cm`, `max_jump_cm` y el suavizado con el HC-SR04 real.
- Verificar el cableado y el brillo de los LEDs físicos.
- Comprobar el divisor de tensión del pin ECHO en placas de 3.3 V.

## 13. Solución de problemas

| Problema | Solución |
|---|---|
| "Cámara: sin cámara" | cierre otras apps que usen la cámara (Teams, Zoom); compruebe `vision.camera_index` |
| Gestos que parpadean o no se detectan | más luz; ajuste los ratios (sección 5); suba `min_frames` |
| Juego lento | `vision.model_complexity: 0`, ocultar panel con `C` |
| `pip` falla instalando mediapipe | asegúrese de usar Python 3.11 de 64 bits (`py -3.11`) |
| Arduino "error - no se pudo conectar" | ¿la laptop está en la red GestureFighter? ¿IP/puerto correctos? |
