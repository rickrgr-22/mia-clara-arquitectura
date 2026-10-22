// MIA Clara · Arquitectura: navegación por lecciones, progreso, búsqueda, explorador de archivos,
// catálogo de APIs y examen. Sin dependencias salvo Mermaid para los diagramas.
(function () {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const leer = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } };
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const lecciones = $$('.leccion');
  const leidas = new Set(leer('mia-arq-leidas', []));

  // ------------------------------------------------------------------ tema
  const tema = leer('mia-arq-tema', null);
  if (tema) document.documentElement.dataset.theme = tema;
  $('#tema').addEventListener('click', () => {
    const oscuro = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = oscuro ? 'light' : 'dark';
    guardar('mia-arq-tema', document.documentElement.dataset.theme);
    dibujarDiagramas(true);
  });

  // ------------------------------------------------------------------ menú
  const menu = $('#menu');
  let grupo = null;
  lecciones.forEach((l, i) => {
    if (l.dataset.grupo !== grupo) {
      grupo = l.dataset.grupo;
      menu.insertAdjacentHTML('beforeend', `<h4>${esc(grupo)}</h4>`);
    }
    menu.insertAdjacentHTML('beforeend',
      `<a href="#${l.id}" data-id="${l.id}"><span class="num"><span>${i}</span></span>${esc(l.dataset.titulo)}</a>`);
    // Botones al final de cada lección
    const sig = lecciones[i + 1];
    const ant = lecciones[i - 1];
    l.insertAdjacentHTML('beforeend', `<div class="marcar">
      <button class="boton secundario" data-marcar="${l.id}"></button>
      <span>${ant ? `<a class="boton secundario" href="#${ant.id}">← ${esc(ant.dataset.titulo)}</a>` : ''}
      ${sig ? `<a class="boton" href="#${sig.id}">${esc(sig.dataset.titulo)} →</a>` : ''}</span></div>`);
  });

  function pintarProgreso() {
    $$('#menu a').forEach((a) => a.classList.toggle('leido', leidas.has(a.dataset.id)));
    $$('[data-marcar]').forEach((b) => { b.textContent = leidas.has(b.dataset.marcar) ? '✓ Lección completada' : 'Marcar como completada'; });
    const pct = Math.round((leidas.size / lecciones.length) * 100);
    $('#progreso i').style.width = pct + '%';
    $('#progreso-texto').textContent = `${leidas.size} de ${lecciones.length} lecciones · ${pct} %`;
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-marcar]');
    if (!b) return;
    const id = b.dataset.marcar;
    leidas.has(id) ? leidas.delete(id) : leidas.add(id);
    guardar('mia-arq-leidas', [...leidas]);
    pintarProgreso();
  });

  // ------------------------------------------------------------------ router
  function mostrar() {
    const [id, ancla] = decodeURIComponent(location.hash.slice(1) || lecciones[0].id).split('/');
    const l = document.getElementById(id) && document.getElementById(id).classList.contains('leccion') ? document.getElementById(id) : lecciones[0];
    lecciones.forEach((x) => x.classList.toggle('visible', x === l));
    $$('#menu a').forEach((a) => a.classList.toggle('activo', a.dataset.id === l.id));
    document.title = `${l.dataset.titulo} · MIA Clara · Arquitectura`;
    document.body.classList.remove('menu-abierto');
    dibujarDiagramas(false);
    if (ancla && document.getElementById(ancla)) document.getElementById(ancla).scrollIntoView();
    else window.scrollTo(0, 0);
  }
  addEventListener('hashchange', mostrar);
  $('#abrir-menu').addEventListener('click', () => document.body.classList.toggle('menu-abierto'));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.body.classList.remove('menu-abierto'); });

  // ------------------------------------------------------------------ diagramas (Mermaid)
  $$('.mermaid').forEach((m) => { m.dataset.fuente = m.innerHTML; });
  let temaMermaid = null;
  function dibujarDiagramas(forzar) {
    if (!window.mermaid) return;
    const oscuro = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    const t = oscuro ? 'dark' : 'neutral';
    if (t !== temaMermaid) {
      temaMermaid = t;
      forzar = true;
      window.mermaid.initialize({
        startOnLoad: false, theme: t, securityLevel: 'strict', fontFamily: 'Inter, sans-serif',
        flowchart: { curve: 'basis', htmlLabels: true }, sequence: { mirrorActors: false },
        themeVariables: oscuro ? { primaryColor: '#2e2615', primaryBorderColor: '#e3c574', lineColor: '#b7b0a8' }
                               : { primaryColor: '#f8efd8', primaryBorderColor: '#8c6914', lineColor: '#57534e' },
      });
    }
    const pendientes = $$('.leccion.visible .mermaid').filter((m) => forzar || !m.dataset.dibujado);
    pendientes.forEach((m) => { m.removeAttribute('data-processed'); m.innerHTML = m.dataset.fuente; m.dataset.dibujado = '1'; });
    if (pendientes.length) window.mermaid.run({ nodes: pendientes }).catch((e) => console.warn('Mermaid', e));
  }
  window.addEventListener('load', () => dibujarDiagramas(true));

  // ------------------------------------------------------------------ copiar código
  $$('pre').forEach((p) => {
    const b = document.createElement('button');
    b.className = 'copiar'; b.type = 'button'; b.textContent = 'Copiar';
    b.addEventListener('click', () => {
      const texto = p.innerText.replace(/^Copiar\n?/, '').replace(/Copiar$/, '');
      navigator.clipboard?.writeText(texto).then(() => { b.textContent = '¡Copiado!'; setTimeout(() => (b.textContent = 'Copiar'), 1400); });
    });
    p.appendChild(b);
  });

  // ------------------------------------------------------------------ explorador de archivos
  const ARCHIVOS = window.ARCHIVOS || [];
  const filtro = { texto: '', repo: '', capa: '' };
  const capas = [...new Set(ARCHIVOS.map((a) => a.k))].sort();
  const selCapa = $('#filtro-capa');
  if (selCapa) capas.forEach((c) => selCapa.insertAdjacentHTML('beforeend', `<option>${esc(c)}</option>`));

  function arbolDe(lista) {
    const raiz = {};
    lista.forEach((a) => {
      const partes = a.p.split('/');
      let n = raiz;
      partes.slice(0, -1).forEach((p) => { n[p] = n[p] || {}; n = n[p]; });
      (n.__archivos = n.__archivos || []).push(a);
    });
    return raiz;
  }
  function htmlArbol(nodo, abierto) {
    const carpetas = Object.keys(nodo).filter((k) => k !== '__archivos').sort();
    let h = '';
    carpetas.forEach((c) => {
      const total = contar(nodo[c]);
      h += `<details class="carpeta"${abierto ? ' open' : ''}><summary>${esc(c)}/ <span class="meta">${total}</span></summary>${htmlArbol(nodo[c], abierto)}</details>`;
    });
    (nodo.__archivos || []).sort((a, b) => a.p.localeCompare(b.p)).forEach((a) => {
      h += `<div class="archivo" id="f-${esc(a.r + ':' + a.p)}"><code>${esc(a.p.split('/').pop())}</code><span class="capa">${esc(a.k)}</span>${a.l ? `<span class="meta">${a.l} líneas</span>` : ''}<p>${esc(a.d)}</p></div>`;
    });
    return h;
  }
  function contar(n) { return (n.__archivos || []).length + Object.keys(n).filter((k) => k !== '__archivos').reduce((s, k) => s + contar(n[k]), 0); }

  function pintarExplorador() {
    const cont = $('#arbol');
    if (!cont) return;
    const t = filtro.texto.toLowerCase();
    const lista = ARCHIVOS.filter((a) =>
      (!filtro.repo || a.r === filtro.repo) && (!filtro.capa || a.k === filtro.capa) &&
      (!t || a.p.toLowerCase().includes(t) || a.d.toLowerCase().includes(t)));
    $('#contador-archivos').textContent = `${lista.length} de ${ARCHIVOS.length} archivos`;
    const abierto = !!(t || filtro.capa) || lista.length < 60;
    const repos = [['certificacion', 'integracentro-core (MIA Clara · Certificación)'], ['gestion', 'integracentro-admin (MIA Clara · Gestión)']];
    cont.innerHTML = repos.filter(([r]) => !filtro.repo || filtro.repo === r).map(([r, nombre]) => {
      const propios = lista.filter((a) => a.r === r);
      if (!propios.length) return '';
      return `<div class="raiz"><details open><summary>${esc(nombre)} <span class="meta">${propios.length}</span></summary>${htmlArbol(arbolDe(propios), abierto)}</details></div>`;
    }).join('') || '<p style="padding:16px">Ningún archivo coincide con el filtro.</p>';
  }
  if ($('#filtro-texto')) {
    $('#filtro-texto').addEventListener('input', (e) => { filtro.texto = e.target.value; pintarExplorador(); });
    $('#filtro-repo').addEventListener('change', (e) => { filtro.repo = e.target.value; pintarExplorador(); });
    selCapa.addEventListener('change', (e) => { filtro.capa = e.target.value; pintarExplorador(); });
    pintarExplorador();
  }

  // ------------------------------------------------------------------ catálogo de APIs
  function rutaApi(p) {
    const m = p.match(/src\/app\/(.*)\/route\.ts$/);
    if (!m) return null;
    return '/' + m[1].split('/').filter((x) => !/^\(.*\)$/.test(x)).join('/');
  }
  const apis = ARCHIVOS.filter((a) => a.p.endsWith('/route.ts')).map((a) => {
    const metodos = (a.d.match(/^Route Handler ([A-Z, ]+?) \//) || [])[1] || (a.d.match(/^(GET|POST|PUT|PATCH|DELETE)[^ ]* \//) || [])[1] || '';
    return { ...a, ruta: rutaApi(a.p), metodos };
  });
  function grupoApi(ruta) {
    const s = ruta.split('/')[2] || ruta.split('/')[1];
    return s;
  }
  function pintarApis() {
    const cont = $('#tabla-apis');
    if (!cont) return;
    const repo = $('#apis-repo').value;
    const t = $('#apis-texto').value.toLowerCase();
    const lista = apis.filter((a) => (!repo || a.r === repo) && (!t || a.ruta.toLowerCase().includes(t) || a.d.toLowerCase().includes(t)))
      .sort((a, b) => a.r.localeCompare(b.r) || a.ruta.localeCompare(b.ruta));
    $('#apis-contador').textContent = `${lista.length} endpoints`;
    cont.innerHTML = `<table><thead><tr><th>App</th><th>Ruta</th><th>Grupo</th><th>Qué hace</th></tr></thead><tbody>${
      lista.map((a) => `<tr><td>${a.r === 'certificacion' ? 'Cert.' : 'Gest.'}</td><td><code>${esc(a.ruta)}</code></td><td>${esc(grupoApi(a.ruta))}</td><td>${esc(a.d.replace(/^Route Handler [A-Z, ]+ \/\S+\.\s*/, ''))}</td></tr>`).join('')
    }</tbody></table>`;
  }
  if ($('#tabla-apis')) {
    $('#apis-repo').addEventListener('change', pintarApis);
    $('#apis-texto').addEventListener('input', pintarApis);
    pintarApis();
  }

  // ------------------------------------------------------------------ búsqueda global
  const indice = lecciones.map((l) => ({ id: l.id, titulo: l.dataset.titulo, texto: l.innerText.toLowerCase(), secciones: $$('h2[id], h3[id]', l).map((h) => ({ id: h.id, t: h.textContent })) }));
  const caja = $('#buscar');
  const res = $('#resultados');
  caja.addEventListener('input', () => {
    const q = caja.value.trim().toLowerCase();
    if (q.length < 2) { res.style.display = 'none'; return; }
    const enLecciones = indice.filter((x) => x.texto.includes(q)).slice(0, 8).map((x) => {
      const pos = x.texto.indexOf(q);
      const frag = x.texto.slice(Math.max(0, pos - 50), pos + 80).replace(/\s+/g, ' ');
      const sec = x.secciones.find((s) => s.t.toLowerCase().includes(q));
      return `<a href="#${x.id}${sec ? '/' + sec.id : ''}"><b>${esc(x.titulo)}</b>${sec ? ' · ' + esc(sec.t) : ''}<small>…${esc(frag)}…</small></a>`;
    });
    const enArchivos = ARCHIVOS.filter((a) => a.p.toLowerCase().includes(q)).slice(0, 6).map((a) =>
      `<a href="#archivos" data-archivo="${esc(a.p)}"><b>📄 ${esc(a.p)}</b><small>${esc(a.d.slice(0, 120))}</small></a>`);
    res.innerHTML = [...enLecciones, ...enArchivos].join('') || '<a>Sin resultados</a>';
    res.style.display = 'block';
  });
  res.addEventListener('click', (e) => {
    const a = e.target.closest('[data-archivo]');
    if (a && $('#filtro-texto')) { $('#filtro-texto').value = a.dataset.archivo; filtro.texto = a.dataset.archivo; pintarExplorador(); }
    res.style.display = 'none'; caja.value = '';
  });
  document.addEventListener('click', (e) => { if (!e.target.closest('.buscar')) res.style.display = 'none'; });
  document.addEventListener('keydown', (e) => { if (e.key === '/' && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); caja.focus(); } });

  // ------------------------------------------------------------------ examen
  const PREGUNTAS = window.PREGUNTAS || [];
  const examen = $('#examen-preguntas');
  let aciertos = 0, respondidas = 0;
  if (examen) {
    examen.innerHTML = PREGUNTAS.map((p, i) => `<div class="pregunta" data-i="${i}"><h4>${i + 1}. ${p.q}</h4>${
      p.o.map((o, j) => `<label><input type="radio" name="p${i}" value="${j}">${o}</label>`).join('')}<div class="explicacion">${p.e}</div></div>`).join('');
    examen.addEventListener('change', (e) => {
      const div = e.target.closest('.pregunta');
      if (!div || div.classList.contains('respondida')) return;
      const p = PREGUNTAS[div.dataset.i];
      const j = Number(e.target.value);
      div.classList.add('respondida');
      $$('label', div).forEach((l, k) => { l.classList.toggle('correcta', k === p.c); if (k === j && j !== p.c) l.classList.add('incorrecta'); $('input', l).disabled = true; });
      respondidas++; if (j === p.c) aciertos++;
      $('#marcador').textContent = `Aciertos: ${aciertos} de ${respondidas} respondidas (${PREGUNTAS.length} en total)`;
    });
    $('#marcador').textContent = `${PREGUNTAS.length} preguntas · responde para ver la explicación`;
  }

  pintarProgreso();
  mostrar();
})();
