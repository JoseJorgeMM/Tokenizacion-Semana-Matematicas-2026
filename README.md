# 🧠 Taller IA · Abriendo la Caja Negra
> Taller interactivo para docentes de matemáticas — Medellín 2026

## Estructura del proyecto

```
taller-ia/
├── api/
│   └── index.py          ← Backend FastAPI (modelo de Markov + corpus)
├── static/
│   └── index.html        ← Frontend interactivo
├── vercel.json           ← Configuración de rutas Vercel
├── requirements.txt      ← Dependencias Python
└── README.md
```

---

## 🚀 Despliegue en Vercel (paso a paso)

### 1. Sube el proyecto a GitHub

```bash
git init
git add .
git commit -m "Taller IA - primera versión"
git remote add origin https://github.com/TU_USUARIO/taller-ia.git
git push -u origin main
```

### 2. Conecta con Vercel

1. Ve a [vercel.com](https://vercel.com) → **Add New Project**
2. Importa tu repositorio de GitHub
3. Vercel detecta automáticamente el `vercel.json` — no cambies nada
4. Haz clic en **Deploy**

### 3. Crea la base de datos KV (corpus persistente)

Después del primer deploy:

1. En el dashboard de tu proyecto en Vercel → pestaña **Storage**
2. Clic en **Create Database** → selecciona **KV**
3. Dale un nombre (ej: `taller-corpus`) → **Create**
4. En la pantalla siguiente, clic en **Connect to Project**
5. Vercel inyecta automáticamente las variables de entorno:
   - `KV_REST_API_URL`
   - `KV_REST_API_TOKEN`
6. Ve a **Deployments** → **Redeploy** para que tome las nuevas variables

✅ ¡Listo! El corpus ahora persiste entre sesiones.

---

## 💻 Desarrollo local

### Instalar dependencias

```bash
pip install fastapi httpx pydantic uvicorn
```

### Correr el servidor

```bash
cd taller-ia
uvicorn api.index:app --reload --port 8000
```

Abre en el navegador: http://localhost:8000

> **Nota local:** Sin las variables KV configuradas, el corpus se guarda en memoria
> (se pierde al reiniciar el servidor). Para desarrollo esto está perfecto.

### Configurar el frontend para desarrollo local

En `static/index.html`, línea donde dice:
```javascript
const API = "";   // producción
```
Cambia a:
```javascript
const API = "http://localhost:8000";   // desarrollo local
```
Recuerda revertirlo antes de hacer deploy.

---

## 📡 Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/corpus` | Ver corpus + stats |
| POST | `/api/corpus/add` | Agregar frase |
| DELETE | `/api/corpus/{i}` | Eliminar frase por índice |
| DELETE | `/api/corpus` | Limpiar todo el corpus |
| GET | `/api/model/tokens?phrase=...` | Tokenizar una frase |
| GET | `/api/model/probabilities` | Tabla de probabilidades completa |
| GET | `/api/model/probabilities?word=...` | Probabilidades de una palabra |
| POST | `/api/model/generate` | Generar texto |
| GET | `/api/model/vocabulary` | Vocabulario completo con IDs |
| GET | `/api/health` | Estado de la API |

---

## 🔬 Cómo funciona el modelo

El modelo es una **Cadena de Markov de bigramas**:

1. **Tokenización**: convierte texto → lista de palabras en minúsculas
2. **Entrenamiento**: cuenta pares consecutivos de palabras
3. **Probabilidades**: `P(siguiente | actual) = frecuencia(par) / frecuencia(actual)`
4. **Generación**: selección aleatoria ponderada por probabilidad

Todo el cálculo ocurre en Python puro. Sin librerías de ML.

---

## 📐 Conceptos matemáticos que se trabajan

- **Probabilidad condicional**: P(B|A)
- **Distribuciones de probabilidad discretas**
- **Funciones biyectivas** (vocabulario → índices)
- **Estadística descriptiva** (frecuencias, proporciones)

---

## 🛠 Stack tecnológico

- **Frontend**: HTML + CSS + JavaScript vanilla
- **Backend**: FastAPI (Python)
- **Persistencia**: Vercel KV (Redis serverless)
- **Deploy**: Vercel
