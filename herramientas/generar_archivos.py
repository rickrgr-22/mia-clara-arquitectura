#!/usr/bin/env python3
"""Genera assets/archivos.js: cada archivo versionado de ambos repositorios con su capa y su propósito.

Uso: python3 herramientas/generar_archivos.py ~/Documents/integracentro-core ~/Documents/integracentro-admin
El propósito sale, en este orden, de: una descripción escrita a mano (MANUAL), el comentario de cabecera
del propio archivo y, si no tiene, una regla según su tipo y ubicación.
"""
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, '..', 'assets', 'archivos.js')

# Datos que no deben publicarse aunque aparezcan en un comentario
CENSURA = [
    (re.compile(r'\b(?!0\.0\.0\.0)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d+)?\b'), '<IP>'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '<correo>'),
    (re.compile(r'\b[0-9a-f]{32}\b'), '<id>'),
]

MANUAL = {
    # ------------------------------------------------------------ raíz (ambos)
    '.gitignore': 'Lista de lo que Git no versiona: node_modules, builds de Next.js, estados de Terraform (*.tfstate), .env y llaves. Es la primera defensa para no subir secretos.',
    'Makefile': 'Interfaz única de operación. Cada objetivo (desplegar, infra, app, verificar, dominios, oracle, servidor...) envuelve a Terraform o Ansible. El CD ejecuta exactamente estos mismos objetivos: lo que funciona en tu terminal funciona en el pipeline.',
    'README.md': 'Documento principal: producto, capturas, criterios de la cédula, seguridad, arquitectura, stack, estructura e inicio rápido.',
    'PRESENTACION.md': 'Presentación ejecutiva sin detalles técnicos para directivos y centros.',
    '.github/workflows/ci.yml': 'Pipeline de Integración Continua (runners hospedados de GitHub, Ubuntu): terraform fmt/validate, ansible --syntax-check, tsc + next build + docker build y pruebas con un Postgres desechable. Corre en push y PR a main/dev.',
    '.github/workflows/cd.yml': 'Pipeline de Despliegue Continuo: se dispara con workflow_run cuando CI termina bien en main. Corre en el runner self-hosted del servidor ARM64 (etiqueta oracle): Terraform plan/apply → Ansible (make app) → pruebas de humo. Tiene candados contra PR y forks, concurrency y un lock compartido entre ambos repos.',
    # ------------------------------------------------------------ ansible
    'ansible/ansible.cfg': 'Configuración de Ansible: inventario local, intérprete de Python automático, salida en YAML y sin archivos .retry.',
    'ansible/inventory.ini': 'Inventario: un único host, localhost con conexión local. Ansible no entra por SSH a otro equipo: corre donde está el kubeconfig (tu Mac o el runner del servidor) y habla con la API de Kubernetes.',
    'ansible/ambientes/local.yml': 'Variables del ambiente local (Mac + Minikube). Se carga con -e @ambientes/local.yml desde el Makefile (AMBIENTE=local).',
    'ansible/ambientes/oracle.yml': 'Variables del ambiente de producción (Oracle Cloud + k3s): directorio de Terraform k3s-oracle, contexto kube "oracle", plataforma k3s y construcción de imagen con docker build (k3s usa el Docker del servidor).',
    'ansible/tasks/leer-terraform.yml': 'Tarea reutilizable: terraform init + terraform output -json y registra namespace y nombres de PVC como facts. Es el "contrato" entre Terraform (infraestructura) y Ansible (aplicación).',
    'ansible/files/sepomex.py': 'Script que descarga el Catálogo Nacional de Códigos Postales de Correos de México, calcula su huella y lo convierte para cargarlo en la tabla codigos_postales. No se versiona el catálogo (sus condiciones lo prohíben).',
    'ansible/files/escenario-pruebas/escenario.json': 'Definición declarativa del escenario de pruebas: centros ficticios, su estado de cédula, cuentas (solo hashes) y evidencias que se cargan.',
    'ansible/files/escenario-pruebas/escenario.py': 'Cargador del escenario de pruebas: inserta centros, usuarios, evidencias y dictámenes vía psql dentro del pod de Postgres; deja una marca en la bitácora para no repetir la carga.',
    'ansible/files/escenario-pruebas/generar_evidencias.py': 'Genera las fotografías de muestra (una por subcriterio) con la leyenda "Evidencia de prueba · sin validez oficial".',
    'ansible/templates/ui-aplicacion.yaml.j2': 'Plantilla Jinja2 de los manifiestos de la aplicación: Deployment integracentro-ui (2 réplicas, probes en /login, límites de memoria, PVC montado en /app/expedientes_storage, variables desde Secrets), Service (80→3000) e Ingress NGINX con TLS y body de 30 MB.',
    'ansible/templates/ui-postgres.yaml.j2': 'Plantilla del PostgreSQL de la certificación: Deployment de 1 réplica con estrategia Recreate (el volumen RWO no admite dos pods), PGDATA en subcarpeta, readinessProbe con pg_isready y su Service ClusterIP en el puerto 5432.',
    'ansible/templates/app.yaml.j2': 'Plantilla de los manifiestos de Gestión: Deployment integracentro-admin, Service e Ingress; variables de entorno con la URL de la certificación (pública e interna), token de tareas y Secrets opcionales (SMTP, Telegram, WhatsApp, voz).',
    'ansible/templates/postgres.yaml.j2': 'Plantilla del PostgreSQL propio de Gestión (base "administracion"), con el mismo patrón que la certificación: Recreate, PGDATA en subcarpeta y pg_isready.',
    # ------------------------------------------------------------ infra
    'infra/terraform/cloudflare/outputs.tf': 'Salidas del stack de Cloudflare: id del túnel, direcciones publicadas y el token del conector (marcado sensitive; el Makefile lo guarda en ~/.integracentro/cloudflared-token).',
    'infra/terraform/cloudflare/versions.tf': 'Versiones de Terraform y providers (cloudflare ~> 5.0, random ~> 3.6) y backend local: el estado contiene el secreto del túnel y vive fuera del repo.',
    'infra/terraform/k3s-oracle/providers.tf': 'Provider kubernetes apuntando al contexto "oracle" y backend "kubernetes": el estado de Terraform se guarda como Secret en kube-system del propio clúster, compartido entre tu terminal y el runner.',
    'infra/terraform/local-minikube/providers.tf': 'Igual que k3s-oracle pero con el contexto "minikube": estado en un Secret de kube-system de Minikube.',
    'infra/terraform/oracle/outputs.tf': 'Salidas del servidor: IP pública y el comando SSH listo para usar (el Makefile la usa para correr preparar-servidor.yml).',
    'infra/terraform/oracle/servidor.tf': 'La máquina virtual: VM.Standard.A1.Flex (ARM Ampere) con Ubuntu 24.04, núcleos/memoria/disco parametrizados, IP pública, llave SSH y ignore_changes sobre la imagen para no recrear el servidor cuando Oracle publica una imagen nueva.',
    'infra/terraform/oracle/variables.tf': 'Variables del servidor con validaciones: región mx-queretaro-1, ssh_cidr (prohíbe 0.0.0.0/0), y límites de núcleos (≤4), memoria (≤24 GB) y disco (50–200 GB) de la capa Always Free.',
    'infra/terraform/oracle/versions.tf': 'Provider oci ~> 7.0 con el perfil DEFAULT de ~/.oci/config y backend local fuera del repo.',
    # ------------------------------------------------------------ app (común)
    'Dockerfile': 'Imagen multi-etapa: builder (node:20-alpine, npm ci, next build) y runner mínimo que solo copia la salida standalone, public y .next/static; corre como usuario sin privilegios nextjs (uid 1001) en el puerto 3000.',
    '.dockerignore': 'Excluye del contexto de build node_modules, .next, .git, .env*, pruebas y prototipos: builds más rápidos, imágenes más chicas y sin secretos dentro.',
    'next.config.ts': 'Configuración de Next.js: output "standalone" (servidor Node autocontenido para Docker) y proxyClientMaxBodySize de 26 MB para aceptar evidencias de hasta 25 MB.',
    'package.json': 'Manifiesto npm: scripts (dev, build, start, lint, pruebas) y dependencias. Pocas dependencias a propósito: next, react, pg, nodemailer, pdf-lib, qrcode (y leaflet en la certificación).',
    'package-lock.json': 'Árbol exacto de dependencias con versiones y hashes de integridad. npm ci lo respeta al pie de la letra: builds reproducibles en CI y en Docker.',
    'tsconfig.json': 'Configuración de TypeScript: modo strict, módulos bundler, JSX de React y alias de rutas. CI lo usa con tsc --noEmit para revisar tipos sin compilar.',
    'tailwind.config.ts': 'Configuración de Tailwind (rutas de contenido); la paleta institucional "oro" vive en globals.css con @theme de Tailwind 4.',
    'postcss.config.js': 'PostCSS con el plugin @tailwindcss/postcss: así Next.js procesa Tailwind 4 en el build.',
    'eslint.config.mjs': 'Configuración plana de ESLint con las reglas de Next.js (core-web-vitals y TypeScript).',
    'AGENTS.md': 'Instrucciones para asistentes de IA que genera Next.js 16: avisa que la versión tiene cambios incompatibles y que se consulte la documentación incluida en node_modules.',
    'CLAUDE.md': 'Apunta a AGENTS.md para que Claude Code siga las mismas reglas.',
    '.gitignore@app': 'Ignorados propios de la aplicación Next.js (.next, node_modules, out, .env*, *.tsbuildinfo).',
    'src/proxy.ts': 'Proxy de Next.js 16 (antes "middleware"): en cada petición valida de forma optimista la firma de la cookie, deja pasar rutas públicas, devuelve 401 a APIs sin sesión, redirige al login con ?siguiente= y envía a la versión móvil a los teléfonos.',
    'src/app/layout.tsx': 'Layout raíz (Server Component): <html lang="es">, tipografías, metadatos e íconos. Envuelve a todas las páginas.',
    'src/app/globals.css': 'Estilos globales: importa Tailwind 4 y define con @theme la paleta institucional oro, negro y marfil (una sola fuente de verdad del color).',
    'src/app/page.tsx': 'Ruta "/": redirige al inicio que le corresponde al rol de la sesión (o al login).',
    'src/app/(dashboard)/layout.tsx': 'Layout del grupo de rutas (dashboard): obtiene la sesión en el servidor y, si no es válida, la limpia y manda al login. Todas las pantallas del panel heredan esta guardia.',
    'src/lib/db.ts': 'Acceso a PostgreSQL con un Pool de node-postgres: query() parametrizada (evita inyección SQL) y withTransaction(), que usa una sola conexión para BEGIN/COMMIT/ROLLBACK.',
    'src/lib/auditoria.ts': 'registrarAuditoria(): inserta en bitacora_auditoria quién hizo qué, sobre qué entidad y con qué detalle; acepta el cliente de una transacción para que la bitácora sea atómica con el cambio.',
    'src/lib/validacion.ts': 'Validación de entrada del lado del servidor (texto, correo, rangos, enteros, UUID...) y respuestaError(), que traduce ErrorValidacion a JSON con su código HTTP y oculta los errores internos.',
    'src/lib/api.ts': 'Ayudante fetch heredado de la primera versión (token en localStorage). La aplicación actual usa cookies HttpOnly y llamadas fetch relativas; es código legado.',
    'src/lib/auth/crypto.ts': 'Criptografía central: scrypt para contraseñas, HKDF para derivar claves por propósito desde AUTH_SECRET, AES-256-GCM para secretos en reposo y tokens HMAC-SHA256 para cookies; comparaciones en tiempo constante.',
    'src/lib/auth/session.ts': 'Sesiones: emite cookies preauth (10 min) y sesión (8 h), bloquea tras 5 intentos, y obtenerSesion() revalida en la BD en cada petición (usuario activo, sesion_version, MFA, centro activo). requerirSesion(roles) es la guardia de cada endpoint.',
    'src/lib/auth/flujo.ts': 'Máquina de estados del login: decide el siguiente paso (cambiar contraseña temporal, enrolar MFA o verificar código) y valida la contraseña nueva.',
    'src/lib/auth/permisos.ts': 'RBAC puro sin dependencias: roles SUPERADMIN, REVISOR, ADMIN_CENTRO y LECTOR, y funciones puedeVerCentro, rolesAsignables, puedeGestionarUsuario... Se usa igual en servidor y en cliente.',
    'src/components/ui.tsx': 'Componentes de interfaz reutilizables: Campo, Modal, Boton, Alerta, EstadoBadge y clases comunes de input.',
    'src/components/SesionProvider.tsx': 'Contexto de React con la sesión ya validada en el servidor, para que los componentes cliente sepan el rol y el centro sin otra llamada.',
    'src/components/DashboardLayout.tsx': 'Marco del panel: menú lateral negro y dorado con las opciones que permite el rol, encabezado y contenido.',
    # ------------------------------------------------------------ certificación (específicos)
    'integracentro-ui/README.md': 'README que generó create-next-app; la documentación real está en el README de la raíz.',
    'integracentro-ui/scripts/crear-superadmin.mjs': 'Script de desarrollo local: aplica las migraciones y crea un SUPERADMIN con contraseña temporal (npm run crear-superadmin).',
    'integracentro-ui/pruebas/motores.test.ts': 'Pruebas unitarias (node:test) del motor de certificación y del de pre-certificación con una cédula mínima: obligatorios, umbral de 80 %, escenarios REAL y POTENCIAL.',
    'integracentro-ui/pruebas/carteles.test.ts': 'Pruebas unitarias de la generación de carteles en PDF (que el texto quepa en una página).',
    'integracentro-ui/pruebas/vigencia-acta.test.ts': 'Pruebas unitarias de la vigencia de un año del acta oficial y de los avisos previos al vencimiento.',
    'integracentro-ui/pruebas/bd/migrar.sh': 'Aplica todas las migraciones DOS veces sobre DATABASE_URL: la segunda pasada demuestra que son idempotentes (el despliegue las reaplica todas en cada versión).',
    'integracentro-ui/pruebas/bd/plan-mejora.test.ts': 'Prueba de integración contra Postgres real del plan de mejora: pendientes que salen de la cédula y de la pre-certificación y avisos de vencimiento.',
    'integracentro-ui/pruebas/bd/avisos-rechazo.test.ts': 'Prueba de integración del resumen diario de evidencias rechazadas (que no se repita un aviso).',
    'integracentro-ui/pruebas/bd/carteles.test.ts': 'Prueba de integración de los carteles: textos, instancias de queja por estado y directorio del personal.',
    'integracentro-ui/pruebas/bd/vigencia-acta.test.ts': 'Prueba de integración de la vigencia del acta oficial y sus avisos con datos reales en la BD.',
    'integracentro-ui/src/app/login/page.tsx': 'Pantalla de acceso (Client Component): correo + contraseña, cambio de contraseña temporal, enrolamiento MFA con QR y verificación del código de 6 dígitos; respeta ?siguiente=.',
    'integracentro-ui/src/app/api/auth/login/route.ts': 'POST /api/auth/login: verifica la contraseña con scrypt (o contra un hash ficticio si el correo no existe, para que el tiempo no revele cuentas), aplica el bloqueo por intentos y emite la cookie preauth.',
    'integracentro-ui/src/app/api/auth/logout/route.ts': 'POST /api/auth/logout: borra las cookies de sesión, preauth y centro.',
    'integracentro-ui/src/app/api/cedula/evidencias/route.ts': 'POST /api/cedula/evidencias: recibe la evidencia capturada en vivo. Valida token de captura de un solo uso, tipo real del archivo por sus bytes, tamaño, ubicación del dispositivo contra el radio del centro; guarda el archivo, su SHA-256 y la bitácora en una transacción.',
    'integracentro-ui/src/app/api/cedula/evidencias/[id]/route.ts': 'GET/PATCH/DELETE /api/cedula/evidencias/:id: descarga de la evidencia, dictamen del revisor (cumple/no cumple, vigencia del documento) y retiro de evidencias pendientes por el centro.',
    'integracentro-ui/src/app/api/centros/[id]/route.ts': 'PATCH/DELETE /api/centros/:id: edición de datos y ubicación del centro y baja lógica (solo SUPERADMIN).',
    'integracentro-ui/src/app/api/centros/[id]/borrar/route.ts': 'GET/POST /api/centros/:id/borrar: vista previa y borrado DEFINITIVO de un centro dado de baja, en Gestión (red interna) y aquí, con la función SQL borrar_centro.',
    'integracentro-ui/src/app/api/certificacion/condicion-fisica/route.ts': 'PUT /api/certificacion/condicion-fisica: el revisor califica de 0 a 3 los cuatro aspectos de cada área física (1.15 a 1.24) o marca que el centro no cuenta con el área.',
    'integracentro-ui/src/app/api/expedientes/route.ts': 'POST /api/expedientes: carga heredada de expedientes (antes de la captura en vivo por subcriterio).',
    'integracentro-ui/src/app/api/expedientes/download/route.ts': 'GET /api/expedientes/download: descarga heredada de expedientes validando centro y rol.',
    'integracentro-ui/src/app/api/plan-mejora/route.ts': 'GET/POST/PUT/DELETE /api/plan-mejora: plan de mejora del centro (acciones con responsable, fecha compromiso y avance).',
    'integracentro-ui/src/app/api/servicio/acceso/[id]/route.ts': 'GET /api/servicio/acceso/:id (entre servicios, con SERVICIO_TOKEN): Gestión reconfirma cada minuto si la cuenta sigue activa y qué centros administra.',
    'integracentro-ui/src/app/api/servicio/centros/[id]/personal/route.ts': 'GET/POST /api/servicio/centros/:id/personal (entre servicios): Gestión lista y da de alta administradores del centro; las cuentas viven aquí.',
    'integracentro-ui/src/app/api/servicio/personal/[id]/route.ts': 'PATCH /api/servicio/personal/:id (entre servicios): baja, reactivación o restablecimiento de contraseña/MFA de un administrador pedido desde la consola de Gestión.',
    'integracentro-ui/src/app/api/usuarios/[id]/route.ts': 'PATCH/DELETE /api/usuarios/:id: edición y baja de usuarios respetando puedeGestionarUsuario y que siempre quede un administrador activo.',
    'integracentro-ui/src/app/api/usuarios/[id]/restablecer/route.ts': 'POST /api/usuarios/:id/restablecer: genera contraseña temporal y/o reinicia el MFA; sube sesion_version para cerrar sus sesiones.',
    'integracentro-ui/src/app/api/usuarios/[id]/superadmin/route.ts': 'POST /api/usuarios/:id/superadmin: convierte a un usuario en superadministrador conservando contraseña y MFA.',
    'integracentro-ui/src/app/actas/[id]/page.tsx': 'Acta imprimible (Server Component): resultado congelado del acta, porcentaje por área, firma del revisor, huella SHA-256 y código QR; marca de agua MUESTRA en las simulaciones.',
    'integracentro-ui/src/app/actas/verificar/[id]/page.tsx': 'Validación del QR: solo un revisor autenticado ve si el acta es válida, alterada (la huella no coincide) o inexistente.',
    'integracentro-ui/src/app/m/layout.tsx': 'Layout de la versión móvil (/m): viewport y metadatos para el teléfono del administrador del centro.',
    'integracentro-ui/src/app/m/page.tsx': 'Inicio móvil: monta InicioMovil.',
    'integracentro-ui/src/app/m/InicioMovil.tsx': 'Pantalla de inicio de la versión móvil: avance del centro y accesos grandes a la cédula, la pre-certificación y el plan de mejora.',
    'integracentro-ui/src/app/m/cedula/page.tsx': 'Ruta /m/cedula: monta CedulaMovil.',
    'integracentro-ui/src/app/m/cedula/CedulaMovil.tsx': 'Cédula en el teléfono: lista de actividades por área con su estado y botón para capturar evidencia.',
    'integracentro-ui/src/app/m/capturar/[codigo]/page.tsx': 'Ruta /m/capturar/:codigo: monta la captura en vivo de un subcriterio.',
    'integracentro-ui/src/app/m/capturar/[codigo]/CapturaMovil.tsx': 'Contenedor de la captura móvil de un subcriterio: pide el token de captura y muestra CapturaEvidencia.',
    'integracentro-ui/src/app/m/plan-mejora/page.tsx': 'Plan de mejora en la versión móvil (reutiliza el componente PlanMejora).',
    'integracentro-ui/src/app/m/precertificacion/page.tsx': 'Pre-certificación en la versión móvil (reutiliza el componente Precertificacion).',
    'integracentro-ui/src/components/movil/CapturaEvidencia.tsx': 'Captura en vivo con getUserMedia (cámara) y la API de geolocalización; comprime la foto o arma un PDF con varias páginas y lo envía con la ubicación y el token.',
    'integracentro-ui/src/components/movil/ShellMovil.tsx': 'Marco de la versión móvil: barra superior, navegación inferior y enlace a la versión de escritorio.',
    'integracentro-ui/src/components/FormUbicacion.tsx': 'Formulario de domicilio con mapa Leaflet + OpenStreetMap: código postal, geocodificación, pin arrastrable y círculo del radio de tolerancia.',
    'integracentro-ui/src/components/PlanMejora.tsx': 'Componente del plan de mejora (escritorio y móvil): pendientes, responsable, fecha compromiso y avance.',
    'integracentro-ui/src/components/Precertificacion.tsx': 'Cuestionario de pre-certificación (96 preguntas en 15 áreas) con guardado por respuesta y resultado por área.',
    'integracentro-ui/src/lib/certificacion/actas.ts': 'Construcción, huella SHA-256 (JSON canónico) y guardado inmutable de las actas (SIMULACION u OFICIAL).',
    'integracentro-ui/src/lib/certificacion/datos.ts': 'Carga desde la BD la entrada del motor de certificación (secciones, criterios, conteo de evidencias aprobadas/pendientes vigentes y condición física).',
    'integracentro-ui/src/lib/evidencias/gps.ts': 'Reglas de la evidencia: tamaños máximos, detección del formato por "números mágicos" (no por la extensión), lectura de la ubicación del dispositivo y cálculo de distancia (haversine) contra el radio del centro con precisión ≤ 100 m.',
    'integracentro-ui/src/lib/precertificacion/datos.ts': 'Acceso a datos de la pre-certificación: preguntas, respuestas del centro e historial de resultados.',
    'integracentro-ui/src/lib/usuarios.ts': 'Reglas de negocio de usuarios: carga del usuario a modificar y la verificación de que el centro no se quede sin administrador activo.',
    'integracentro-ui/src/app/(dashboard)/documentos/page.tsx': 'Ruta heredada /documentos: redirige a la cédula, donde ahora se organizan las evidencias.',
    'integracentro-ui/src/app/actas/BarraAcciones.tsx': 'Barra de acciones del acta que no se imprime: volver al panel e imprimir o guardar como PDF.',
    # ------------------------------------------------------------ prototipos
    'index-mobile.html': 'Prototipo HTML estático (Tailwind por CDN) de la primera idea de la interfaz móvil. No se despliega; se conserva como antecedente de diseño.',
    'index-mobile-black.html': 'Prototipo HTML estático, variante oscura de la interfaz móvil. No se despliega.',
    'index-desktop-black.html': 'Prototipo HTML estático, variante oscura del portal de escritorio. No se despliega.',
    'index-black2-desktop.html': 'Segunda iteración del prototipo de escritorio. No se despliega.',
    'index-black2-mobile.html': 'Segunda iteración del prototipo móvil. No se despliega.',
    'docs/DESPLIEGUE.md': 'Guía de despliegue: capas (Ansible prerrequisitos, Terraform, Ansible aplicación), secretos, migraciones, pipeline, primera vez en la Mac, operación y escenario de pruebas.',
    'docs/referencias/cedula-supervision-estancia-temporal-ayuda-mutua-vf1.pdf': 'Documento normativo de referencia: Cédula de Supervisión VF1 (6 áreas, 51 criterios, 65 actividades). Es la "especificación" del dominio.',
    # ------------------------------------------------------------ gestión (específicos)
    'docs/MANUAL-ADMINISTRADOR.md': 'Manual del administrador del centro: uso paso a paso de cada módulo de Gestión.',
    'docs/GUIA-CAPACITACION.md': 'Guía para capacitar al personal con el centro de prueba sin afectar centros reales.',
    'web/public/formatos/sisvea-ctng-2024.pdf': 'Formato oficial en blanco del cuestionario SISVEA 2024; pdf-lib escribe encima con coordenadas para respetar el diseño oficial.',
    'web/src/app/sso/callback/route.ts': 'POST /sso/callback: recibe el pase firmado por la certificación, verifica la firma Ed25519, emisor, audiencia, vigencia de 60 s, que el jti no se haya usado (sso_pases_usados) y el valor "estado" de la cookie; luego crea la sesión local.',
    'web/src/lib/auth/session.ts': 'Sesiones de Gestión con varias "puertas" (personal por SSO, familiares, encargados con PIN, consejeros, médicos con MFA) y reconfirmación del acceso del personal con la certificación cada minuto (tolera 5 min si no responde).',
    'web/src/lib/auth/crypto.ts': 'Misma criptografía que la certificación (scrypt, HKDF, AES-256-GCM, HMAC) con su propio AUTH_SECRET: un secreto comprometido no sirve en la otra aplicación.',
    'web/src/lib/db.ts': 'Pool de node-postgres hacia el PostgreSQL de Gestión, query() parametrizada y withTransaction().',
    'web/src/lib/red.ts': 'Panorama de la red de centros para el superadministrador: une los centros de la certificación con los indicadores locales.',
    'web/src/lib/borrar-centro.ts': 'Borrado definitivo de un centro o de un servidor llamando a las funciones SQL borrar_centro y borrar_servidor.',
    'web/src/lib/expedientes/documentos.ts': 'Carga de un documento del expediente validando que pertenezca al centro de la sesión.',
    'web/src/lib/expedientes/internos.ts': 'Lectura de internos y familiares, cambio de familiar responsable y formato de la duración de la estancia.',
    'web/src/lib/expedientes/modulos.ts': 'Catálogo de módulos contratables por centro y guardias tieneModulo/guardiaModulo que protegen pantallas y APIs.',
    'web/src/lib/expedientes/pdf.ts': 'Generación con pdf-lib del PDF del documento firmado: texto con el marcado de la plantilla, trazos de las firmas, nombres, fechas y huella SHA-256.',
    'web/src/lib/pagos/cobros.ts': 'Cobros: credenciales de Mercado Pago cifradas por centro (AES-256-GCM), configuración de cuotas semanales/mensuales y generación de cargos.',
    'web/src/lib/padrinos/acceso.ts': 'Guardias del portal de consejeros y de su administración.',
    'web/src/lib/sisvea/datos.ts': 'Acceso a datos del cuestionario SISVEA: lectura, guardado parcial y armado de los datos que llenan el PDF oficial.',
    'web/src/lib/tiendita/guardia.ts': 'Guardias de la tiendita (encargado o administrador) y de los depósitos (solo administrador).',
    'web/src/lib/unidad/acceso.ts': 'Guardias de Unidad y Servicio: quién ve cada servicio (responsables, coordinadores, administración).',
    'web/src/lib/visitas/acceso.ts': 'Guardias de visitas para la administración y para los consejeros.',
    'web/src/lib/validacion.ts': 'Validación de entrada del servidor y respuestaError(), igual que en la certificación.',
    'web/src/lib/auditoria.ts': 'registrarAuditoria() sobre la bitácora propia de Gestión (sin datos sensibles).',
    'web/src/components/FirmaPad.tsx': 'Lienzo de firma con el dedo o lápiz (canvas + pointer events) que exporta los trazos para el PDF.',
    'web/src/components/FormularioEsquema.tsx': 'Formulario generado a partir de un esquema (secciones y campos), usado por la valoración clínica para validar igual en cliente y servidor.',
    'web/src/components/clinico/MapaCorporal.tsx': 'Mapa corporal SVG para marcar tatuajes, heridas y cicatrices numeradas.',
    'web/src/components/clinico/Medicos.tsx': 'Lista y alta de médicos del centro con acceso y restablecimiento de MFA.',
    'web/src/components/expedientes/Articulos.tsx': 'Artículos de uso personal: selección en el alta, registro de entregas en el expediente y edición de la lista del centro.',
    'web/src/components/expedientes/DomicilioCP.tsx': 'Captura de domicilio por código postal: llena entidad y municipio y ofrece las colonias del catálogo.',
    'web/src/components/expedientes/FormInterno.tsx': 'Formulario de alta del interno y su familiar responsable (ficha de ingreso).',
    'web/src/components/expedientes/Telegram.tsx': 'Conexión del familiar a Telegram (QR o correo) y bitácora de mensajes enviados.',
    'web/src/components/padrinos/AccesoPin.tsx': 'Acceso con usuario y PIN de 4 dígitos en teclado grande (consejeros y servidores).',
    'web/src/components/padrinos/visitas.tsx': 'Visitas del consejero a sus personas en consejería.',
    'web/src/components/tiendita/CapturaTiendita.tsx': 'Venta en la tiendita paso a paso: persona, productos con foto, total y saldo; si no alcanza, no se entrega.',
    'web/src/components/ui.tsx': 'Componentes de interfaz reutilizables de Gestión (Campo, Modal, Boton...).',
    'web/src/app/page.tsx': 'Ruta "/": manda a cada perfil a su inicio o a la pantalla de acceso del personal.',
    'web/src/app/login/page.tsx': 'Acceso del personal: botón "Entrar con mi cuenta de MIA Clara" que inicia el SSO, y accesos a las otras puertas.',
    'web/src/app/familias/page.tsx': 'Puerta del Portal de familias: correo y contraseña sin MFA (con bloqueo por intentos).',
    'web/src/app/caja/page.tsx': 'Puerta del encargado de tiendita y lavandería: usuario recordado en el equipo y PIN en teclado grande.',
    'web/src/app/medicos/page.tsx': 'Puerta de los médicos: correo, contraseña y código TOTP; primera vez cambia la contraseña y enrola MFA.',
    'web/src/app/portal/PortalCliente.tsx': 'Portal de familias: saldos, cargos con botón de pago (Mercado Pago), recibos, visitas, medicamentos y conexión a Telegram.',
    'web/src/app/firma/[id]/FirmaCliente.tsx': 'Firma en tableta a pantalla completa: cada firmante confirma la lectura y firma; al reunir todas se genera el PDF.',
    'web/src/app/estado-de-cuenta/[id]/page.tsx': 'Estado de cuenta imprimible por interno (cargos, recibos y movimientos de monederos).',
    'integracentro-ui/src/app/(dashboard)/perfil/AvisosTelegram.tsx': 'Tarjeta de "Mi perfil" para conectar o desconectar los avisos por Telegram con un enlace de un solo uso.',
    'integracentro-ui/src/app/recuperar/[token]/FormNuevaPassword.tsx': 'Formulario cliente para definir la contraseña nueva con el enlace de recuperación (valida longitud y confirmación).',
    'web/src/app/(dashboard)/centros/[id]/FichaCentro.tsx': 'Ficha del centro para el superadministrador: indicadores, administradores (sus cuentas viven en la certificación), familiares con portal, módulos y estado de Mercado Pago y correo.',
    'web/src/app/(dashboard)/clinico/[id]/ExpedienteClinico.tsx': 'Expediente clínico de un interno: valoración de ingreso por secciones, mapa corporal, firma del médico, notas médicas y parte clínica del egreso.',
    'web/src/app/(dashboard)/tiendita/Submenu.tsx': 'Submenú de la tiendita: vender, catálogo y reporte.',
    'web/src/app/portal/Encabezado.tsx': 'Encabezado del Portal de familias (marfil y plata) con el nombre del familiar y el botón de salir.',
    'web/src/app/recibos/[id]/page.tsx':'Recibo de efectivo imprimible con folio, importe con letra y dos tantos.',
}

# Capas para filtrar en el explorador
def capa(ruta):
    if ruta.startswith('.github/'): return 'CI/CD'
    if ruta.startswith('infra/'): return 'Infraestructura (Terraform)'
    if ruta.startswith('ansible/'): return 'Automatización (Ansible)'
    if ruta.startswith('docs/') or ruta.endswith('.md'): return 'Documentación'
    if re.search(r'/db/[^/]+\.sql$', ruta): return 'Datos (migraciones SQL)'
    if '/pruebas/' in ruta: return 'Pruebas'
    if '/src/app/api/' in ruta or ruta.endswith('/route.ts'): return 'Backend (API)'
    if '/src/lib/' in ruta or ruta.endswith('/proxy.ts'): return 'Backend (lógica)'
    if '/src/' in ruta or '/public/' in ruta: return 'Frontend'
    if ruta.endswith(('Dockerfile', '.dockerignore')): return 'Contenedores'
    if ruta in ('Makefile',): return 'Automatización (Ansible)'
    if ruta.startswith('index'): return 'Prototipos'
    return 'Configuración'


def ruta_web(ruta):
    """De .../src/app/(dashboard)/x/[id]/page.tsx obtiene /x/[id]."""
    m = re.search(r'src/app/(.*)/[^/]+$', ruta)
    if not m: return '/'
    partes = [p for p in m.group(1).split('/') if not (p.startswith('(') and p.endswith(')'))]
    return '/' + '/'.join(partes)


def por_regla(ruta, info):
    base = os.path.basename(ruta)
    ext = os.path.splitext(base)[1].lower()
    nombre = os.path.splitext(base)[0]
    com = info.get('c', '')
    if ruta.startswith('docs/img/'):
        if base == 'mia-ac.jpg': return 'Logotipo de MIA AC usado en los README.'
        return f'Captura de pantalla «{re.sub(r"^\d+-", "", nombre).replace("-", " ")}» que ilustra el README (datos de demostración).'
    if '/escenario-pruebas/evidencias/' in ruta:
        return f'Fotografía de muestra del subcriterio {nombre} para el escenario de pruebas (leyenda «sin validez oficial»), generada por generar_evidencias.py.'
    if base == '.terraform.lock.hcl':
        return 'Candado de providers de Terraform: versiones exactas y hashes. Garantiza que terraform init descargue siempre lo mismo (reproducibilidad y protección de la cadena de suministro). Se versiona.'
    if '/public/tiendita/' in ruta:
        return f'Ilustración genérica sin marca ({nombre}) del catálogo inicial de la tiendita.'
    if '/public/marca/' in ruta: return 'Logotipo de MIA AC servido como archivo estático (también es el ícono del navegador).'
    if re.search(r'/public/(file|globe|next|vercel|window)\.svg$', ruta):
        return 'Ícono de la plantilla de create-next-app; no se usa en la interfaz.'
    if base in ('icon.png', 'apple-icon.png'):
        return 'Ícono de la aplicación; Next.js lo detecta por convención de nombre y genera las etiquetas <link rel="icon">.'
    if ext == '.sql':
        tablas = info.get('tablas', '')
        return ('Migración idempotente (se reaplica en cada despliegue). ' + com + (f' Crea: {tablas}.' if tablas else '')).strip()
    if base == 'route.ts':
        metodos = ', '.join(x for x in info.get('ex', []) if x in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'))
        api = ruta_web(ruta)
        return f'Route Handler {metodos} {api}. ' + (com or 'Valida la sesión y el rol con la guardia correspondiente, toma el centro de la sesión y responde JSON.')
    if base == 'page.tsx':
        r = ruta_web(ruta)
        if com: return f'Página {r}. {com}'
        return f'Página {r} (Server Component): valida la sesión y el rol en el servidor y entrega los datos iniciales al componente cliente de la pantalla.'
    if base == 'layout.tsx':
        return f'Layout de {ruta_web(ruta)}: marco común y guardia de acceso para las rutas que contiene. ' + com
    if re.search(r'Cliente\.tsx$', base):
        pantalla = ruta_web(ruta)
        return f'Componente cliente ("use client") de la pantalla {pantalla}: estado, formularios, tablas y llamadas fetch a la API. ' + com
    if ext in ('.tsx', '.ts') and com:
        return com
    if ext in ('.tsx',):
        return f'Componente React {nombre}.'
    if ext in ('.ts',):
        ex = ', '.join(info.get('ex', [])[:5])
        return f'Módulo TypeScript {nombre}' + (f' (exporta {ex}).' if ex else '.')
    if com: return com
    return ''


def leer_repo(raiz, nombre_repo, cabeceras):
    archivos = subprocess.run(['git', 'ls-files'], cwd=raiz, capture_output=True, text=True, check=True).stdout.split('\n')
    salida = []
    for ruta in filter(None, archivos):
        info = cabeceras.get(ruta, {})
        # Claves manuales: ruta exacta, ruta sin el prefijo de la app (integracentro-ui/ o web/), o el nombre base
        sin_app = re.sub(r'^(integracentro-ui|web)/', '', ruta)
        desc = MANUAL.get(ruta) or (MANUAL.get(sin_app) if sin_app != ruta else None)
        if not desc and ruta in ('integracentro-ui/.gitignore', 'web/.gitignore'): desc = MANUAL['.gitignore@app']
        if not desc and sin_app != ruta and os.path.basename(ruta) in MANUAL and '/' not in sin_app: desc = MANUAL[os.path.basename(ruta)]
        if not desc: desc = por_regla(ruta, info)
        if not desc: desc = 'Archivo de soporte del repositorio.'
        salida.append({'r': nombre_repo, 'p': ruta, 'l': info.get('lines', 0), 'k': capa(ruta), 'd': desc})
    return salida


def cabeceras_de(raiz):
    """Comentario de cabecera, líneas y exportaciones de cada archivo de texto."""
    datos = {}
    archivos = subprocess.run(['git', 'ls-files'], cwd=raiz, capture_output=True, text=True, check=True).stdout.split('\n')
    for ruta in filter(None, archivos):
        p = os.path.join(raiz, ruta)
        ext = os.path.splitext(ruta)[1].lower()
        info = {'lines': 0, 'c': '', 'ex': []}
        if ext in ('.png', '.jpg', '.jpeg', '.pdf', '.ico', '.webp', '.svg', '.docx', '.gif') or not os.path.isfile(p):
            datos[ruta] = info
            continue
        try:
            texto = open(p, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            datos[ruta] = info
            continue
        lineas = texto.split('\n')
        info['lines'] = len(lineas)
        com = []
        for l in lineas[:80]:
            s = l.strip()
            if not com and (s == '' or s.startswith(("'use client'", '"use client"', 'import ', '---', '#!'))):
                continue
            m = re.match(r'^(//+|#+|--|\*|/\*\*?|<!--)\s?(.*)', s)
            if m:
                t = m.group(2).strip().rstrip('*/').strip().strip('=').strip()
                if t: com.append(t)
                if len(' '.join(com)) > 420: break
            else:
                break
        info['c'] = ' '.join(com)[:460]
        # Los comentarios pueden traer datos que no deben publicarse
        for patron, reemplazo in CENSURA:
            info['c'] = patron.sub(reemplazo, info['c'])
        info['ex'] = re.findall(r'export (?:async )?(?:default )?(?:function|const|class|type|interface) (\w+)', texto)[:8]
        if ext == '.sql':
            tablas = re.findall(r'create table if not exists (\w+)', texto, re.I)
            funciones = re.findall(r'create (?:or replace )?function (\w+)', texto, re.I)
            info['tablas'] = ', '.join(tablas + [f + '()' for f in funciones])
        datos[ruta] = info
    return datos


def main():
    core, admin = sys.argv[1], sys.argv[2]
    todos = leer_repo(core, 'certificacion', cabeceras_de(core)) + leer_repo(admin, 'gestion', cabeceras_de(admin))
    with open(SALIDA, 'w', encoding='utf-8') as f:
        f.write('// Generado por herramientas/generar_archivos.py: no editar a mano.\n')
        f.write('window.ARCHIVOS = ')
        json.dump(todos, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print(f'{len(todos)} archivos -> {SALIDA}')


if __name__ == '__main__':
    main()
