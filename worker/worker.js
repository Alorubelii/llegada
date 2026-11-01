/**
 * Llegada · servidor intermedio (Cloudflare Worker, plan gratuito).
 *
 * Por qué hace falta: Renfe no deja que una web de otro dominio lea sus datos
 * desde el navegador (CORS). Este Worker los pide por la app, los guarda unos
 * segundos en caché para no saturar a Renfe y los devuelve con permiso CORS.
 *
 * Rutas:
 *   GET /flota      posiciones y retrasos de AVE, Avant, Alvia, MD y Regionales
 *   GET /cercanias  posiciones de Cercanías y Rodalies
 *   GET /avisos     incidencias de Adif (todos los operadores) y de Renfe Cercanías
 *   GET /salud      comprobación rápida
 *
 * Variables (wrangler.toml → [vars]):
 *   ORIGENES  dominios que pueden usarlo, separados por comas
 *             ej. "https://rubenmanchatrans-design.github.io"
 */

const FUENTES = {
  flota: { url: "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json", ttl: 15 },
  cercanias: { url: "https://tiempo-real.renfe.com/renfe-visor/flota.json", ttl: 15 },
};
const ADIF_RED = "https://www.adif.es/viajeros/estado-de-la-red";
const RENFE_AVISOS = "https://gtfsrt.renfe.com/alerts.json";
const UA = "Mozilla/5.0 (compatible; Llegada/1.0; +https://github.com/)";

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const cors = corsHeaders(req, env);
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "GET") return json({ error: "Solo GET" }, 405, cors);
    if (cors === null) return json({ error: "Origen no permitido" }, 403, {});

    try {
      const ruta = url.pathname.replace(/\/+$/, "") || "/";
      if (ruta === "/salud") return json({ ok: true, hora: new Date().toISOString() }, 200, cors);
      if (ruta === "/flota" || ruta === "/cercanias") return await proxy(FUENTES[ruta.slice(1)], cors, ctx);
      if (ruta === "/avisos") return await avisos(cors, ctx);
      return json({ error: "Ruta no encontrada", rutas: ["/flota", "/cercanias", "/avisos", "/salud"] }, 404, cors);
    } catch (e) {
      return json({ error: "No se han podido leer los datos de origen", detalle: String(e && e.message || e) }, 502, cors);
    }
  },
};

function corsHeaders(req, env) {
  const origin = req.headers.get("Origin");
  const permitidos = (env.ORIGENES || "*").split(",").map(s => s.trim()).filter(Boolean);
  const base = { "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Max-Age": "86400", Vary: "Origin" };
  if (permitidos.includes("*")) return { ...base, "Access-Control-Allow-Origin": "*" };
  if (!origin) return base; // peticiones directas (curl, navegador) sin CORS
  if (permitidos.includes(origin)) return { ...base, "Access-Control-Allow-Origin": origin };
  return null;
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...headers } });
}

/* Caché compartida de Cloudflare: como mucho una petición a Renfe cada `ttl` segundos */
async function cached(key, ttl, ctx, producir) {
  const cache = caches.default;
  const req = new Request("https://cache.llegada/" + key);
  const hit = await cache.match(req);
  if (hit) return hit.text();
  const body = await producir();
  ctx.waitUntil(cache.put(req, new Response(body, { headers: { "Cache-Control": `public, max-age=${ttl}` } })));
  return body;
}

async function proxy(f, cors, ctx) {
  const body = await cached(f.url, f.ttl, ctx, async () => {
    const r = await fetch(f.url + "?v=" + Date.now(), { headers: { "User-Agent": UA, Accept: "application/json" } });
    if (!r.ok) throw new Error("Renfe respondió " + r.status);
    const text = await r.text();
    JSON.parse(text); // si Renfe cambia el formato, mejor fallar aquí que en el móvil
    return text;
  });
  return new Response(body, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=10", ...cors } });
}

async function avisos(cors, ctx) {
  const body = await cached("avisos", 120, ctx, async () => {
    const [adif, renfe] = await Promise.allSettled([leerAdif(), leerRenfe()]);
    const lista = [...(adif.status === "fulfilled" ? adif.value : []), ...(renfe.status === "fulfilled" ? renfe.value : [])];
    return JSON.stringify({
      actualizado: new Date().toISOString(),
      fuentes: { adif: adif.status === "fulfilled", renfe: renfe.status === "fulfilled" },
      avisos: lista,
    });
  });
  return new Response(body, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=60", ...cors } });
}

const GRAVE = /suspendid|interrumpid|cortad|sin servicio|cancelad/i;

/* Página pública de Adif "Estado de la red": cada aviso es un <article class="aviso-item">.
   Si Adif cambia su web, esta función devuelve una lista vacía y la app lo indica. */
async function leerAdif() {
  const r = await fetch(ADIF_RED, { headers: { "User-Agent": UA, Accept: "text/html" } });
  if (!r.ok) throw new Error("Adif " + r.status);
  const out = [];
  let actual = null;
  const texto = s => s.replace(/\s+/g, " ").trim();
  await new HTMLRewriter()
    .on("article.aviso-item", { element() { actual = { titulo: "", texto: "", ambito: "" }; out.push(actual); } })
    .on("article.aviso-item .aviso-card__titulo", { text(t) { if (actual) actual.titulo += t.text; } })
    .on("article.aviso-item .aviso-card__content", { text(t) { if (actual) actual.texto += t.text; } })
    .on("article.aviso-item .aviso-item__ambito", { text(t) { if (actual) actual.ambito += t.text; } })
    .transform(r).arrayBuffer();
  return out
    .map(a => ({ titulo: texto(a.titulo), texto: texto(a.texto).slice(0, 400), fecha: texto(a.ambito), fuente: "Adif · estado de la red" }))
    .filter(a => a.titulo)
    .map(a => ({ ...a, grave: GRAVE.test(a.titulo + " " + a.texto) }));
}

/* Avisos GTFS-RT de Renfe (Cercanías): solo los activos ahora */
async function leerRenfe() {
  const r = await fetch(RENFE_AVISOS, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error("Renfe avisos " + r.status);
  const j = await r.json();
  const ahora = Date.now() / 1000;
  const tr = t => (t && t.translation && (t.translation.find(x => x.language === "es") || t.translation[0]) || {}).text || "";
  return (j.entity || [])
    .map(e => e.alert)
    .filter(a => a && (!a.activePeriod || a.activePeriod.some(p => (!p.start || +p.start <= ahora) && (!p.end || +p.end >= ahora))))
    .slice(0, 20)
    .map(a => {
      const titulo = tr(a.headerText) || tr(a.descriptionText).slice(0, 90);
      const texto = tr(a.descriptionText);
      return { titulo, texto: texto === titulo ? "" : texto.slice(0, 400), fecha: "", fuente: "Renfe Cercanías", grave: GRAVE.test(titulo + " " + texto) };
    })
    .filter(a => a.titulo);
}
