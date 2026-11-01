# Llegada · trenes en directo

App web para el móvil (se instala como una app) que muestra los trenes de Renfe de Alta Velocidad, Larga y Media Distancia en el mapa, con su retraso real.

**Qué hace**

- **Inicio personal**: te saluda por tu nombre y te enseña de un vistazo tus trayectos guardados con el próximo tren y su retraso, los trenes que sigues y las próximas salidas de tu estación.
- **Mapa**: todos los trenes en circulación, coloreados por retraso, sobre las vías dibujadas. Se mueven con suavidad al actualizarse. Filtros por tipo de tren, búsqueda por número, ciudad o estación, y Cercanías opcional con datos en directo.
- **Ficha de cada tren**: próxima parada, hora corregida con el retraso, recorrido completo, puntualidad del último mes, botón de avisos, "voy a recogerlo" y compartir por WhatsApp la hora de llegada.
- **Estación**: próxima salida o llegada destacada, lista con estado real, filtro por destino, estaciones favoritas, "cerca de mí" y guardar el trayecto en Inicio.
- **Recoger a alguien**: tren, estación y lo que tardas en llegar, y te dice a qué hora salir de casa. Se recalcula solo.
- **Tú**: nombre, estación de casa, favoritas, trayectos, avisos, tema claro u oscuro, puntualidad de la red, avisos de Adif y de dónde salen los datos. Todo se guarda solo en el móvil.
- **Bienvenida** la primera vez para elegir tu estación.

**Lo que no puede hacer (y por qué)**

- Iryo y Ouigo no publican la posición de sus trenes. Solo aparecen a través de los avisos de Adif.
- Renfe no tiene una API documentada. La app lee los mismos ficheros que usa el visor oficial de Renfe; si Renfe cambia el formato, hay que adaptar el servidor.
- La puntualidad es una aproximación: el retraso máximo visto en lecturas cada 15 minutos.

---

## Cómo está montado

```
src/app.html          la app (una sola página, sin dependencias)
tools/build_data.py   genera estaciones, horario del día y puntualidad desde el GTFS oficial de Renfe
tools/bundle.py       mete los datos dentro de index.html
tools/capturar.py     guarda una lectura de posiciones (para la puntualidad)
worker/worker.js      servidor intermedio en Cloudflare (gratis)
.github/workflows/    tareas automáticas: horarios cada madrugada y lecturas cada 15 min
```

La app funciona en tres niveles y siempre muestra en la barra superior cuál está usando:

1. **En directo** (punto verde): a través de tu servidor en Cloudflare. Se actualiza cada 20 segundos.
2. **Retraso ~30 min** (punto ámbar): sin servidor, lee una copia pública que alguien mantiene en GitHub.
3. **Instantánea** (punto azul): sin conexión, usa las últimas posiciones guardadas dentro de la propia página.

---

## Puesta en marcha (unos 15 minutos)

### 1. Subir el proyecto a GitHub

Crea un repositorio nuevo llamado `llegada` en tu cuenta `Alorubelii` y sube todo el contenido de esta carpeta.

```
git init
```

```
git add .
```

```
git commit -m "Llegada"
```

```
git branch -M main
```

```
git remote add origin https://github.com/Alorubelii/llegada.git
```

```
git push -u origin main
```

### 2. Activar GitHub Pages con Actions

En el repositorio: **Settings → Pages → Source: GitHub Actions**.

Después: **Settings → Actions → General → Workflow permissions → Read and write permissions**.

### 3. Crear el servidor en Cloudflare

Necesitas una cuenta gratuita de Cloudflare.

```
npm install -g wrangler
```

```
cd worker
```

```
wrangler login
```

```
wrangler deploy
```

Al terminar te dará una dirección como `https://llegada.TU-USUARIO.workers.dev`. Comprueba que responde:

```
https://llegada.TU-USUARIO.workers.dev/salud
```

Si tu web de GitHub Pages tiene otra dirección, cámbiala en `worker/wrangler.toml` (`ORIGENES`) y vuelve a lanzar `wrangler deploy`.

### 4. Conectar la app con el servidor

En el repositorio: **Settings → Secrets and variables → Actions → Variables → New repository variable**.

- Nombre: `LLEGADA_API`
- Valor: la dirección del paso anterior, sin barra final

Luego ve a **Actions → Horarios del día y publicar → Run workflow**. En un par de minutos la app estará en:

```
https://alorubelii.github.io/llegada/
```

### 5. Instalarla en el móvil

Abre esa dirección en el móvil. En Android: menú del navegador → **Instalar app**. En iPhone: **Compartir → Añadir a pantalla de inicio**. En iPhone las notificaciones solo funcionan con la app instalada así.

---

## Mantenimiento

Todo es automático:

- Cada madrugada se descargan los horarios oficiales de Renfe y se vuelve a publicar la app.
- Cada 15 minutos se guarda una lectura de posiciones; con 7 días o más, la puntualidad pasa a calcularse con tus propios datos (últimos 30 días). El histórico se borra solo pasados 45 días.

Para probar cambios en tu ordenador:

```
python3 tools/bundle.py --fecha 2026-11-01 --standalone --out index.html
```

```
python3 -m http.server 8000
```

Y abre `http://localhost:8000`.

## Siguientes pasos posibles

- **Avisos con la app cerrada** (Web Push): ahora los avisos llegan con la app abierta o en segundo plano. Para recibirlos con el móvil bloqueado y la app cerrada hay que añadir Web Push al Worker (claves VAPID y una tarea programada que revise los trenes seguidos).
- **Cercanías en el mapa**: el servidor ya expone `/cercanias`; falta dibujarlo en la app.
- **Publicarla**: si quieres abrirla al público, conviene revisar las condiciones de uso de los datos de Renfe y poner un dominio propio.

Proyecto independiente, sin relación con Renfe ni Adif.
