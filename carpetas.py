"""Carpetas y subcarpetas SIN IA: el árbol de ~/Projects/ig-saved/carpetas.py
(aprobado por Nacho el 29/09/2026), rellenado con palabras clave ES/EN.

Es un bibliotecario con una lista de etiquetas: no entiende el vídeo, solo
lee las palabras de la descripción, los #hashtags, el @usuario y, si hay, los
subtítulos de TikTok (palabra a palabra desde el 01/10/2026: ver «El motor» más
abajo). Por eso falla donde hace falta "ver" el vídeo (el género de una escena
de película, por ejemplo). La calidad medida está en docs/diseno.md (decisiones 5
y 10; tests/test_precision.py y tools/medir.py).

  rutas("Receta de tarta de queso al horno", "", "cocinaconana")
  -> (["recetas/postres"], "")

Devuelve 1-3 rutas, la principal primero, y la ciudad si es un sitio.
Si la persona pega su clave de Gemini, ia.py las rehace como carpetas.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
import rules  # noqa: E402  (copia de ig-saved/rules.py: las palabras clave de las carpetas grandes)

# --- el árbol, igual que SUB en ig-saved/carpetas.py (29/09/2026) ---
SUB = {
    "sitios": ["asiatico", "italiano", "hamburguesas", "espanola", "restaurantes", "bares", "cafes", "hoteles",
               "museos", "planes", "naturaleza", "tiendas"],
    "viajes": ["destinos", "trucos"],
    "recetas": ["platos", "postres", "saludables", "rapidas", "bebidas"],
    "pelis_series": ["comedia", "accion", "drama", "terror", "scifi", "animacion", "series", "recomendaciones",
                     "explicaciones"],
    "anime": ["escenas", "edits", "recomendaciones", "explicaciones"],
    "tecnologia": ["ia", "ia_noticias", "asistentes", "programacion", "automatizaciones", "prompts", "webs", "apps",
                   "gadgets"],
    "finanzas": ["inversion", "trading", "dinero", "quant"],
    "carrera": ["practicas", "estudio", "universidad"],
    "videojuegos": ["trucos", "recomendaciones"],
    "moda": ["outfits", "cuidado"],
    "fitness_salud": ["entreno", "salud"],
    "humor": ["memes", "sketches", "clips"],
}
SUELTAS = ["musica", "ciencia", "negocios", "coches", "diseño", "deportes", "hogar", "motivacion", "animales", "otros"]
CARPETAS = list(SUB) + SUELTAS
VALIDAS = {f"{c}/{s}" for c, ss in SUB.items() for s in ss} | set(SUELTAS)

# rules.py tiene sus propias carpetas grandes; estas dos cambian de nombre en el árbol
RENOMBRA = {"planes": "sitios", "estudios": "carrera"}

# Palabras de más para las carpetas grandes (se suman a las de rules.py).
EXTRA = {
    "sitios": [" restaurante", " restaurant", " donde comer", " dónde comer", " sitio ", " sitios ", " local ",
               " reserva", " carta ", " menú", " menu ", " degustación", " omakase", " foodie", " foodies",
               " comerenmadrid", " restaurantesmadrid", " madridfood", " planesmadrid", " cenarenmadrid",
               " food spot", " hidden gem", " must try", " best food", " bar ", " bares ", " cafetería",
               " cafeteria", " coffee shop", " heladería", " pastelería", " hotel ", " museo", " museum",
               " tienda", " store ", " shop ", " abre ", " ha abierto", " abierto", " opening", " nuevo local",
               " ticket medio", " precio medio", " por persona", "📍", " calle ", " c/ ", " avenida", " plaza ",
               " tokyofood", " japanfood", " eatwith", " eats", " brunch", " buffet", " michelin", " dinner",
               " lunch", " cenar", " comer en", " restaurantes"],
    "viajes": [" travel", " viajar", " guía de", " itinerario", " días en", " days in", " visit ", " visitar"],
    "humor": [" humor", " comedy", " jajaja", " 😂", "🤣", " xd ", " lmao", " memes"],
    "pelis_series": [" peli ", " pelis ", " film", " movie", " series"],
    "tecnologia": [" claude", " cursor", " n8n", " agente", " agent", " chatbot", " gpt", " vibe cod"],
    "carrera": [" estudiar", " study", " exam", " examen", " universidad", " university", " notes", " apuntes"],
}

# Subcarpetas: palabras de cada una. Sin ninguna, la más común de la carpeta (POR_DEFECTO).
SUB_KW = {
    "sitios/asiatico": [" sushi", " ramen", " japon", " japanese", " japo", " nikkei", " chino", " chinese", " china ",
                        " coreano", " korean", " thai", " tailand", " vietnam", " pho ", " dim sum", " dumpling",
                        " gyoza", " wok", " asiatic", " asiático", " asian", " izakaya", " yakiniku", " wagyu",
                        " tempura", " udon", " katsu", " bao ", " omakase", " nigiri", " maki", " handroll",
                        " poke", " curry", " indio", " indian", " tokyo", " tokio", " osaka", " kyoto", " seoul",
                        " bangkok", " teppanyaki", " robata", " sake ", " miso"],
    "sitios/italiano": [" pizza", " pizzer", " pasta", " italiano", " italiana", " italian", " trattoria",
                        " risotto", " burrata", " carbonara", " lasagn", " gelato", " napolitan", " neapolitan",
                        " tiramis", " focaccia", " osteria"],
    "sitios/hamburguesas": [" burger", " hamburgues", " smash", " bocadillo", " bocata", " sandwich", " sándwich",
                            " hot dog", " hotdog", " perrito", " fast food", " comida rápida", " pollo frito",
                            " fried chicken", " kebab", " shawarma", " tacos", " taco ", " burrito", " pita"],
    "sitios/espanola": [" tapas", " tapa ", " taberna", " asador", " cocido", " tortilla", " croqueta", " jamón",
                        " jamon", " paella", " arroz", " marisco", " gallego", " vasco", " pintxo", " pincho",
                        " sidrería", " sidra", " vermut", " vermú", " callos", " torrezno", " chuletón", " chuleton",
                        " cachopo", " casa de comidas", " menú del día", " menu del dia", " castizo", " tradicional",
                        " de toda la vida", " bravas", " zamburiñ", " pulpo", " gamba", " brasa", " parrilla"],
    "sitios/bares": [" bar ", " bares ", " copas", " copa ", " cóctel", " coctel", " cocktail", " speakeasy",
                     " discoteca", " club ", " nightclub", " fiesta", " party", " rooftop", " terraza", " cervec",
                     " cerveza", " beer", " pub ", " drinks", " gin", " vinoteca", " wine bar", " azotea"],
    "sitios/cafes": [" café", " cafe ", " cafetería", " cafeteria", " coffee", " brunch", " desayuno", " breakfast",
                     " pastelería", " pasteleria", " bakery", " panadería", " croissant", " helado", " heladería",
                     " ice cream", " gelato", " churros", " tarta", " cake", " cheesecake", " dulce", " matcha",
                     " specialty coffee", " merienda", " pancake", " gofre", " waffle", " cookies", " donut"],
    "sitios/hoteles": [" hotel", " hostal", " resort", " alojamiento", " airbnb", " habitación", " suite ",
                       " spa ", " glamping", " cabaña", " boutique hotel", " noche en", " night in", " stay "],
    "sitios/museos": [" museo", " museum", " exposición", " exposicion", " exhibition", " galería", " gallery",
                      " monumento", " catedral", " palacio", " castillo", " templo", " temple", " teatro"],
    "sitios/planes": [" plan ", " planazo", " experiencia", " experience", " actividad", " activity",
                      " escape room", " karting", " bolera", " mercado", " market", " concierto", " festival",
                      " parque de atracciones", " taller", " workshop", " clase de", " qué hacer", " que hacer",
                      " things to do", " ocio"],
    "sitios/naturaleza": [" playa", " beach", " cala ", " ruta", " senderismo", " hike", " hiking", " mirador",
                          " montaña", " mountain", " lago", " lake", " cascada", " waterfall", " piscina natural",
                          " naturaleza", " nature", " parque natural", " bosque", " sunset", " atardecer"],
    "sitios/tiendas": [" tienda", " store", " shop ", " shopping", " outlet", " compras", " boutique", " mercadillo",
                       " vintage", " segunda mano", " thrift", " showroom", " librería", " bookstore", " concept store"],
    "sitios/restaurantes": [" mexican", " mexicano", " tacos", " fusión", " fusion", " libanés",
                            " griego", " peruano", " peruvian", " argentino", " carne", " steak", " entrecot",
                            " buffet", " michelin", " degustación", " tasting menu", " vegano", " vegan"],

    "viajes/trucos": [" truco", " trick", " hack", " tip", " consejo", " vuelo", " flight", " billete", " barato",
                      " cheap", " maleta", " equipaje", " luggage", " aeropuerto", " airport", " seguro de viaje",
                      " ryanair", " skiplagged", " pasaporte", " visado", " esim", " ahorrar", " save money"],
    "viajes/destinos": [" destino", " destination", " isla", " island", " visitar", " visit", " lugares",
                        " places", " pueblo", " ciudad", " city", " playa", " beach", " país", " country",
                        " japón", " japan", " italia", " italy", " bucket list", " bucketlist", " paisaje"],

    "recetas/postres": [" postre", " dessert", " tarta", " cake", " bizcocho", " galleta", " cookie", " brownie",
                        " chocolate", " flan", " helado", " ice cream", " cheesecake", " crepe", " tiramis",
                        " dulce", " sweet", " muffin", " magdalena", " donut", " natillas", " pancake", " tortitas",
                        " caramelo", " azúcar", " sugar", " torrija", " churros", " pastel", " mousse"],
    "recetas/bebidas": [" cóctel", " coctel", " cocktail", " bebida", " drink", " smoothie", " batido", " zumo",
                        " juice", " limonada", " lemonade", " café", " coffee", " matcha", " tea ", " te verde", " te chai", " te helado",
                        " mojito", " margarita", " sangría", " sangria", " spritz", " gin tonic", " latte"],
    "recetas/saludables": [" saludable", " healthy", " proteína", " proteica", " protein", " fit ", " fitness",
                           " light", " sin azúcar", " sugar free", " calorías", " calorias", " calories", " macros",
                           " low carb", " keto", " vegano", " vegan", " ensalada", " salad", " dieta", " diet",
                           " meal prep", " mealprep", " avena", " oats", " bowl"],
    "recetas/rapidas": [" rápida", " rapida", " rápido", " rapido", " fácil", " facil", " easy", " quick",
                        " minutos", " minutes", " min ", " sencilla", " simple", " airfryer", " air fryer",
                        " freidora de aire", " microondas", " microwave", " 3 ingredientes", " pocos ingredientes",
                        " en 5", " en 10", " en 15", " lazy", " sin horno"],
    "recetas/platos": [" pasta", " arroz", " rice", " pollo", " chicken", " carne", " beef", " pescado", " fish",
                       " salmón", " salmon", " guiso", " stew", " sopa", " soup", " lasaña", " lasagna", " pizza",
                       " hamburguesa", " burger", " tacos", " curry", " ramen", " cena", " dinner", " comida",
                       " lunch", " huevo", " egg", " patata", " potato", " guisado", " al horno"],

    "pelis_series/series": [" serie ", " series", " season", " temporada", " episode", " episodio", " capítulo",
                            " show ", " tvshow", " tv show", " sitcom", " hbo", " netflix series", " breaking bad",
                            " the office", " friends", " succession", " snowfall", " the boys", " game of thrones",
                            " juego de tronos", " peaky blinders", " the sopranos", " dexter", " better call saul",
                            " stranger things", " house of the dragon", " euphoria", " suits", " mentalist",
                            " south park", " family guy", " simpson", " cobra kai", " the bear", " invincible"],
    "pelis_series/terror": [" terror", " horror", " miedo", " scary", " creepy", " suspense",
                            " paranormal", " exorcis", " conjuring", " scream", " haunted",
                            " zombie", " slasher"],
    "pelis_series/scifi": [" sci-fi", " scifi", " ciencia ficción", " science fiction", " marvel", " mcu", " dc ",
                           " superhero", " superhéroe", " avengers", " spider", " batman", " superman", " x-men",
                           " xmen", " star wars", " starwars", " jedi", " interstellar", " dune", " matrix",
                           " alien", " fantasy", " fantasía", " harry potter", " lord of the rings", " señor de los anillos",
                           " magneto", " thanos", " iron man", " deadpool", " wolverine", " avatar", " time travel"],
    "pelis_series/animacion": [" animación", " animacion", " animation", " animated", " pixar", " disney",
                               " dreamworks", " cartoon", " dibujos", " shrek", " toy story", " ghibli", " kung fu panda"],
    "pelis_series/comedia": [" comedia", " comedy", " funny", " hilarious", " gracioso",
                             " stifler", " american pie", " anchorman", " superbad", " hangover", " resacón",
                             " adam sandler", " jim carrey", " parody", " parodia", " laugh"],
    "pelis_series/accion": [" acción", " accion", " action", " fight", " pelea", " gangster", " mafia", " crime",
                            " crimen", " heist", " atraco", " war ", " guerra", " soldier", " hitman", " assassin",
                            " john wick", " tarantino", " guy ritchie", " gun", " shootout", " police", " policía",
                            " agent", " spy", " espía", " bond", " thriller", " revenge", " venganza", " cartel", " drug", " prison", " mission impossible", " fast and furious"],
    "pelis_series/drama": [" drama", " romance", " romántic", " romantic", " love story", " amor", " sad ",
                           " triste", " llorar", " cry", " tragedy", " emotional", " heartbreak", " trauma",
                           " relationship", " oscar"],
    "pelis_series/recomendaciones": [" recomend", " recommend", " pelis que", " películas que", " peliculas que",
                                     " movies to watch", " must watch", " watchlist", " qué ver", " que ver",
                                     " quever", " top 5", " top 10", " películas para", " movies that",
                                     " letterboxd", " goodfilms", " findingoodfilms"],
    "pelis_series/explicaciones": [" explica", " explain", " curiosidad", " curiosidades", " detalle", " detail",
                                   " sabías que", " did you know", " behind the scenes", " detrás de las cámaras",
                                   " teoría", " theory", " análisis", " analysis", " easter egg", " director", " missed", " never noticed",
                                   " hidden", " making of",
                                   " why ", " por qué", " facts", " fact ", " details", " detalles",
                                   " kubrick", " nolan", " filming", " rodaje", " cinematograf"],

    "anime/edits": [" edit", " amv", " edits", " editz", " capcut", " ae ", " aftereffects", " 4k", " phonk"],
    "anime/recomendaciones": [" recomend", " recommend", " must watch", " best anime", " underrated",
                              " anime recommendation",
                              " mejores anime", " qué anime", " animes que", " anime to watch"],
    "anime/explicaciones": [" explica", " explain", " teoría", " theory", " curiosidad", " lore", " análisis",
                            " analysis", " did you know", " sabías", " por qué", " why "],
    "anime/escenas": [" escena", " scene", " episode", " episodio", " capítulo", " moment", " momento", " clip"],

    "tecnologia/asistentes": [" chatgpt", " claude", " gemini", " copilot", " gpt", " perplexity", " grok",
                              " claude code", " claudecode", " anthropic", " openai", " comandos", " commands",
                              " custom gpt", " proyectos de claude", " skills", " mcp"],
    "tecnologia/programacion": [" python", " javascript", " código", " codigo", " code ", " coding", " programar",
                                " programación", " programacion", " programming", " developer", " dev ", " github",
                                " repo", " api ", " vercel", " react", " sql", " backend", " frontend",
                                " computer science", " cursor", " vibe coding", " vibecoding", " terminal", " linux"],
    "tecnologia/automatizaciones": [" automatiz", " automation", " automate", " n8n", " make.com", " zapier",
                                    " workflow", " flujo", " bot ", " agente", " agent", " agents", " agentes"],
    "tecnologia/prompts": [" prompt", " prompts", " prompting", " instrucciones para", " copy this", " copia este"],
    "tecnologia/webs": [" web ", " webs", " website", " página web", " pagina web", " sitio web", " herramienta online",
                        " .com", " framer", " webflow", " free website", " sites", " páginas", " websites", " web gratis",
                        " useful websites", " webs útiles", " webs que", " navegador", " browser", " extension", " extensión"],
    "tecnologia/apps": [" app ", " apps ", " aplicación", " aplicacion", " iphone", " android", " app store",
                        " appstore", " ios ", " móvil", " movil", " phone"],
    "tecnologia/gadgets": [" gadget", " gadgets", " macbook", " ipad", " airpods", " auriculares", " headphones",
                           " cámara", " camera", " dron", " drone", " dji", " ray-ban", " rayban", " meta glasses",
                           " gafas", " monitor", " teclado", " keyboard", " setup", " laptop", " portátil",
                           " carplay", " nintendo", " switch", " tablet", " smartwatch", " apple watch", " kindle"],
    "tecnologia/ia_noticias": [" nuevo modelo", " new model", " lanza", " launch", " released", " acaba de",
                               " just dropped", " anuncia", " announced", " noticia", " news", " benchmark",
                               " deepseek", " gpt-5", " gpt5", " o3", " sora", " veo 3", " nvidia", " agi"],
    "tecnologia/ia": [" aitools",
                      " ai tools", " aitool", " midjourney", " heygen", " elevenlabs", " notebooklm", " ai video", " video ai"],

    "finanzas/trading": [" trading", " trader", " trade", " day trading", " forex", " scalping", " velas",
                         " candlestick", " chart", " gráfico", " opciones", " options", " futuros", " futures"],
    "finanzas/quant": [" quant", " quantitative", " cuantitativ", " algorithm", " algoritm", " backtest",
                       " python", " modelo", " model", " hedge fund", " renaissance", " jane street", " citadel",
                       " estadística", " statistic", " machine learning"],
    "finanzas/inversion": [" invert", " invest", " inversión", " inversion", " acciones", " stock", " etf", " s&p",
                           " sp500", " bolsa", " dividend", " cartera", " portfolio", " fondo indexado", " index fund",
                           " warren buffett", " buffett", " cripto", " bitcoin", " interés compuesto", " compound"],
    "finanzas/dinero": [" dinero", " money", " ahorr", " save ", " saving", " sueldo", " salario", " salary",
                        " nómina", " gastos", " presupuesto", " budget", " deuda", " debt", " hipoteca", " impuestos",
                        " tax", " millonario", " rico", " rich", " finanzas personales", " personal finance", " banco"],

    "carrera/practicas": [" prácticas", " practicas", " internship", " intern ", " cv ", " curriculum", " currículum",
                          " resume", " entrevista", " interview", " linkedin", " trabajo", " job", " empleo",
                          " hiring", " recruiter", " banca de inversión", " investment banking", " goldman",
                          " jp morgan", " consulting", " consultoría", " mckinsey", " career", " carrera profesional"],
    "carrera/universidad": [" universidad", " university", " uni ", " college", " harvard", " stanford", " mit ",
                            " ivy league", " admisión", " admission", " grado", " degree", " máster", " master",
                            " beca", " scholarship", " campus", " ie university", " erasmus"],
    "carrera/estudio": [" estudiar", " study", " studying", " estudio", " examen", " exam", " apuntes", " notes",
                        " memorizar", " memorize", " concentración", " focus", " productividad", " productivity",
                        " técnica", " pomodoro", " notion", " obsidian", " aprender", " learn", " leer", " reading"],

    "videojuegos/recomendaciones": [" recomend", " recommend", " mejores juegos", " best games", " top ", " review",
                                    " análisis", " noticia", " news", " trailer", " lanzamiento", " release",
                                    " nuevo juego", " new game", " gta 6", " gta vi", " juegos que", " games to play"],
    "videojuegos/trucos": [" truco", " trick", " tips", " guía", " guide", " how to", " secret", " secreto",
                           " glitch", " bug", " hack", " build", " mazo", " deck", " estrategia", " strategy"],

    "moda/cuidado": [" pelo", " hair", " piel", " skin", " skincare", " crema", " cream", " perfume", " fragancia",
                     " fragrance", " colonia", " barba", " beard", " minoxidil", " corte de pelo", " haircut",
                     " barber", " peluquer", " dientes", " teeth", " acné", " acne", " sérum", " serum", " glowup",
                     " jawline", " maquillaje", " makeup", " manicura", " nails", " cuidado personal", " grooming"],
    "moda/outfits": [" outfit", " ootd", " ropa", " clothes", " look ", " style", " estilo", " fashion", " moda",
                     " zapatillas", " sneaker", " camisa", " shirt", " pantalón", " jeans", " chaqueta", " jacket",
                     " old money", " streetwear", " zara", " vinted", " reloj", " watch", " rolex"],

    "fitness_salud/entreno": [" gym", " entreno", " entrenamiento", " workout", " ejercicio", " exercise",
                              " músculo", " muscle", " pesas", " rutina", " routine", " cardio", " correr",
                              " running", " abdominales", " abs ", " sentadilla", " squat", " press banca",
                              " bench", " fuerza", " strength", " calistenia", " hipertrofia", " glúteo"],
    "fitness_salud/salud": [" salud", " health", " dormir", " sleep", " sueño", " médico", " doctor", " dieta",
                            " diet", " nutrición", " nutrition", " vitamina", " vitamin", " estrés", " stress",
                            " ansiedad", " anxiety", " postura", " posture", " dolor", " pain", " alergia",
                            " dermat", " mental", " adhd", " tdah", " suplemento", " supplement"],

    "humor/memes": [" meme", " memes", " pov", " when you", " cuando tu", " cuando te", " literally me",
                    " relatable", " me when", " yo cuando", " nobody", " nadie:", " reaction"],
    "humor/sketches": [" sketch", " parodia", " parody", " actuación", " skit", " standup", " stand up",
                       " monólogo", " monologo", " comedia", " comedy", " personaje", " character", " imitación",
                       " imitando", " tipos de", " types of"],
    "humor/clips": [" prank", " broma", " fail", " caída", " cámara oculta", " hidden camera", " real life",
                    " vida real", " vídeo viral", " viral video", " clip", " jajajaja"],
}
POR_DEFECTO = {"sitios": "restaurantes", "viajes": "destinos", "recetas": "platos", "pelis_series": "comedia",
               "anime": "edits", "tecnologia": "ia", "finanzas": "dinero", "carrera": "estudio",
               "videojuegos": "trucos", "moda": "outfits", "fitness_salud": "salud", "humor": "memes"}
# (sin acentos " té " sería "te" y " uñas" "unas": por eso no están)
# subcarpetas que solo valen si hay un sitio concreto que comer (no "sitios/restaurantes" por cualquier "comida")
COMIDA = ["asiatico", "italiano", "hamburguesas", "espanola", "restaurantes"]

# Señales de que el vídeo habla de un SITIO concreto que se puede visitar.
SITIO_FUERTE = re.compile(
    r"📍|(?i:\b(c/|calle|avda\.?|avenida|plaza|paseo|carrer)\s+\S+.{0,30}\d)"
    r"|\b\d{5}\s+[A-ZÁÉÍÓÚ][a-záéíóú]+"                      # código postal + ciudad
    # "Restaurante Casa Pepe" (nombre con mayúscula: antes el re.I global dejaba pasar "restaurante con")
    r"|(?i:\b(restaurante|restaurant|bar|cafeter[ií]a|hotel|museo|tienda))\s+@?[A-Z][\w'’&.-]+"
    r"|(?i:\b(ticket medio|precio medio|por persona|reserva(r)? (en|con)|ubicaci[oó]n|direcci[oó]n|location)\b)")

CIUDADES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Málaga", "Bilbao", "Marbella", "Ibiza", "Mallorca",
            "Palma", "Alicante", "Granada", "Córdoba", "Zaragoza", "San Sebastián", "Donostia", "Santander",
            "Salamanca", "Toledo", "Segovia", "Cádiz", "Tenerife", "Gran Canaria", "Menorca", "Benidorm",
            "Valladolid", "Oviedo", "Gijón", "A Coruña", "Vigo", "Santiago de Compostela", "Pamplona", "Murcia",
            "Lisboa", "Lisbon", "Oporto", "Porto", "París", "Paris", "Londres", "London", "Roma", "Rome", "Milán",
            "Milan", "Florencia", "Florence", "Nápoles", "Naples", "Venecia", "Venice", "Berlín", "Berlin",
            "Ámsterdam", "Amsterdam", "Bruselas", "Brussels", "Praga", "Prague", "Viena", "Vienna", "Budapest",
            "Copenhague", "Copenhagen", "Estocolmo", "Stockholm", "Dublín", "Dublin", "Atenas", "Athens",
            "Estambul", "Istanbul", "Dubái", "Dubai", "Tokio", "Tokyo", "Osaka", "Kioto", "Kyoto", "Seúl", "Seoul",
            "Bangkok", "Singapur", "Singapore", "Hong Kong", "Bali", "Nueva York", "New York", "NYC", "Miami",
            "Los Angeles", "Los Ángeles", "Chicago", "Ciudad de México", "CDMX", "Mexico City", "Buenos Aires",
            "Bogotá", "Lima", "Santiago", "Marrakech", "Mykonos", "Santorini", "Niza", "Nice", "Mónaco", "Monaco"]
_CIU_ALIAS = {"Tokyo": "Tokio", "Lisbon": "Lisboa", "London": "Londres", "Rome": "Roma", "Milan": "Milán",
              "Florence": "Florencia", "Naples": "Nápoles", "Venice": "Venecia", "Berlin": "Berlín",
              "Amsterdam": "Ámsterdam", "Brussels": "Bruselas", "Prague": "Praga", "Vienna": "Viena",
              "Copenhagen": "Copenhague", "Stockholm": "Estocolmo", "Dublin": "Dublín", "Athens": "Atenas",
              "Istanbul": "Estambul", "Dubai": "Dubái", "Kyoto": "Kioto", "Seoul": "Seúl", "Singapore": "Singapur",
              "New York": "Nueva York", "NYC": "Nueva York", "Paris": "París", "Porto": "Oporto",
              "Los Angeles": "Los Ángeles", "CDMX": "Ciudad de México", "Mexico City": "Ciudad de México",
              "Donostia": "San Sebastián", "Nice": "Niza", "Monaco": "Mónaco", "Palma": "Mallorca"}
_CIU_RE = re.compile(r"(?<![\w])(" + "|".join(re.escape(c) for c in sorted(CIUDADES, key=len, reverse=True))
                     + r")(?![\w])", re.I)
_CIU_TAG = re.compile(r"#?(?:comer|cenar|planes|restaurantes|food|eat|bares|brunch|que hacer)?en?("
                      + "|".join(re.escape(c.lower().replace(" ", "")) for c in CIUDADES) + r")\b", re.I)


def ciudad(texto):
    """La ciudad más nombrada del texto ("" si ninguna)."""
    vistos = {}
    for m in _CIU_RE.finditer(texto or ""):
        k = next((c for c in CIUDADES if c.lower() == m.group(1).lower()), m.group(1))
        k = _CIU_ALIAS.get(k, k)
        vistos[k] = vistos.get(k, 0) + 1
    if not vistos:
        for m in _CIU_TAG.finditer(texto or ""):
            k = next((c for c in CIUDADES if c.lower().replace(" ", "") == m.group(1).lower()), None)
            if k:
                k = _CIU_ALIAS.get(k, k)
                vistos[k] = vistos.get(k, 0) + 1
    return max(vistos, key=vistos.get) if vistos else ""



# ---------- el diccionario, afinado (01/10/2026) ----------
# rules.py es compartido con ig-saved y no se toca: aquí se corrige cómo se leen algunas palabras.
ARREGLA = {"resume": " resume ",            # "resume" casaba con "resumen"
           "practica": " practicas ",        # y "practica" con "practicar"
           "stock": " stock",                # y "stock" con "stockholm"
           " health": " health ",            # "healthy" es de recetas saludables, no de salud
           "quant": " quant",                # "quantum" es física
           " car ": " car "}
QUITA = set()

# Palabras de doble sentido o de relleno: cuentan la mitad. Ayudan si no hay nada más, pero
# no ganan a una palabra clara ("history" sale en pelis, memes y ciencia por igual).
DEBILES = {"history", "success", "aesthetic", "universe", "experiment", "shop", "sabias que", "did you know",
           "fun fact", "curiosidad", "dato curioso", "datos curiosos", "productivity", "productividad", "wisdom",
           "math", "abre", "tools", "herramientas", "music", "musica", "song", "design", "business", "school",
           "job", "uni", "sales", "comida", "food", "plato", "calle", "store", "trip", "places", "mercado",
           "planet", "planeta", "science", "edit", "trailer", "scene", "escena", "episode", "season", "abierto",
           "local", "sitio", "sitios", "carta", "menu", "experience", "experiencia", "plan", "planes", "watch",
           "top", "list", "lista", "why", "por que", "details", "detalles", "detail", "detalle", "hidden",
           "director", "missed", "facts", "fact", "based on", "simple", "light", "minutos", "minutes", "min",
           "bowl", "fit", "comida", "cena", "dinner", "lunch", "huevo", "egg", "character", "personaje",
           "real life", "vida real", "clip", "moment", "momento", "drama", "amor", "love", "cry", "sad",
           "mental", "pain", "dolor", "estudio", "learn", "aprender", "leer", "reading", "focus", "tecnica",
           "monitor", "setup", "switch", "camera", "camara", "gafas", "model", "modelo", "chart", "grafico",
           "trade", "save", "rico", "rich", "banco", "news", "noticia", "launch", "lanza", "acaba de",
           "flujo", "bot", "web", "sites", "paginas", "phone", "movil", "style", "estilo", "look",
           "reloj", "watch", "crema", "cream", "routine", "rutina", "fuerza", "strength", "postura", "piel"}

AMPLIA = {
    "fitness_salud": [" pull up", " pullup", " chin up", " dominada", " barra fija", " calistenia", " calisthenics",
                      " press banca", " bench press", " sentadilla", " squat", " hipertrofia", " entreno",
                      " gimnasio", " cardio", " running", " plan de entrenamiento", " ansiedad", " anxiety",
                      " dormir", " sleep", " sistema inmune", " immune", " respiracion", " breathing", " meditacion",
                      " meditation", " estiramiento", " stretching", " movilidad", " mobility", " suplemento",
                      " creatina", " creatine", " medico", " doctor", " fisio"],
    "recetas": [" receta", " recipe", " matcha", " latte", " gin tonic", " smoothie", " batido", " meal prep",
                " mealprep", " airfryer", " air fryer", " freidora", " ingredientes", " ingredients", " homemade",
                " casero", " casera", " al horno", " bake", " baking", " brownie", " galleta", " cookie", " tiramisu",
                " lasagna", " lasana", " paella", " noodles", " risotto", " hummus", " guacamole", " sopa", " soup",
                " ensalada", " salad", " bizcocho", " flan ", " cocinar", " cooking", " how to make", " como hacer",
                " paso a paso", " step by step", " postre", " dessert", " tarta de", " pancake", " tortitas"],
    "tecnologia": [" webs ", " navegador", " browser", " chrome ", " extension", " herramientas de ia", " ai tool",
                   " macbook", " airpods", " react ", " frontend", " backend", " developer", " desarrollador",
                   " n8n", " zapier", " make.com", " supabase", " vercel", " repo ", " github", " open source",
                   " lovable", " programar", " programa en", " ingeniero de software", " software engineer",
                   " engineer", " build in public", " saas", " teclado", " keyboard", " gadget", " unboxing",
                   " midjourney", " heygen", " elevenlabs", " notebooklm", " perplexity", " copilot", " deepseek",
                   " agente de ia", " agentes de ia", " ai agent", " ai agents", " automation", " automate",
                   " workflow", " prompts", " modelo de ia", " ai model"],
    "finanzas": [" banco", " bank ", " comisiones", " hipoteca", " mortgage", " ahorrar", " ahorro", " sueldo",
                 " salario", " salary", " presupuesto", " budget", " fondo indexado", " index fund", " backtest",
                 " broker", " interes compuesto", " compound interest", " nomina", " irpf", " finanzas",
                 " finance", " money", " make money", " ganar dinero", " passive income", " ingresos pasivos",
                 " criptomoneda", " crypto", " trader", " day trading", " forex", " options trading"],
    "pelis_series": [" season", " directed by", " dirigida por", " starring", " protagonizada", " storyline",
                     " plot ", " imdb", " rotten tomatoes", " screenplay", " box office", " taquilla", " villain",
                     " villano", " sequel", " secuela", " remake", " pelis", " peli ", " cinefilo", " moviescene",
                     " filmmaking", " filmmaker", " streaming on", " now streaming", " in theaters", " en cines",
                     " miniserie", " miniseries", " sitcom", " the bear", " breaking bad", " the office",
                     " game of thrones", " peaky blinders", " stranger things", " succession", " the sopranos",
                     " better call saul", " house of the dragon", " euphoria", " suits ", " interstellar",
                     " john wick", " superbad", " toy story", " shrek", " oppenheimer", " barbie",
                     " wolf of wall street", " tarantino", " scorsese", " nolan", " kubrick", " dicaprio",
                     " pitt", " pacino", " de niro", " mcconaughey", " gosling", " cillian"],
    "anime": [" amv", " animeedit", " shonen", " shounen", " seinen", " myanimelist", " studio ghibli", " madhouse",
              " crunchyroll", " waifu", " gojo", " sukuna", " itachi", " zoro", " eren", " tanjiro", " vegeta",
              " bleach", " berserk", " evangelion", " death note", " deathnote", " haikyuu", " spy x family",
              " chainsaw", " mob psycho", " studio pierrot", " toei", " mangaka", " anime movie"],
    "humor": [" pov", " 😂", " 🤣", " 💀", " jajaja", " jaja", " lmao", " lmfao", " xd ", " sketch", " meme",
              " broma", " prank", " camara oculta", " hidden camera", " relatable", " me when", " yo cuando",
              " cuando tu", " when you", " nobody", " nadie", " skit", " humor", " gracioso", " risa"],
    "viajes": [" itinerary", " itinerario", " travel guide", " guia de viaje", " days in", " dias en", " escapada",
               " roadtrip", " road trip", " vuelos", " vuelo", " flights", " maleta", " equipaje", " pasaporte",
               " visado", " esim", " backpacking", " mochilero", " islandia", " iceland", " toscana", " tuscany",
               " bali", " tailandia", " thailand", " paisaje", " destinos", " destino", " viajar", " travel",
               " vacaciones", " ryanair", " skiplagged", " lugares que", " places to visit", " visitar"],
    "carrera": [" study with me", " studywithme", " pomodoro", " memorizar", " apuntes", " admision", " admission",
                " harvard", " ats ", " cv ", " curriculum", " entrevista de trabajo", " job interview", " internship",
                " investment banking", " banca de inversion", " consulting", " consultoria", " mckinsey",
                " recruiter", " linkedin", " prácticas", " estudiar", " studying", " examen", " exams"],
    "videojuegos": [" ps5", " gameplay", " minecraft", " clash royale", " trofeos", " trophies", " gta 6", " gta vi",
                    " videojuegos", " videojuego", " juegazo", " gamer", " gaming", " steam ", " nintendo switch",
                    " speedrun", " fortnite", " valorant", " brawl stars", " pokemon"],
    "moda": [" bolso", " bolsos", " handbag", " outfits", " jeans", " chaqueta", " old money", " skincare",
             " piel grasa", " haircut", " taper", " fade ", " perfume", " fragancia", " colonia", " corte de pelo",
             " barberia", " sneakers", " zapatillas", " streetwear", " fashion", " moda "],
    "coches": [" coche", " coches", " porsche", " gt3", " rueda", " neumatico", " mecanica", " mechanic", " motor ",
               " gato hidraulico", " supercar", " carsoftiktok", " ferrari", " lamborghini", " bmw", " mercedes"],
    "deportes": [" copa del rey", " golazo", " highlights", " lakers", " celtics", " nba", " champions", " vinicius",
                 " mbappe", " futbol", " football", " soccer", " tenis", " padel", " f1 ", " formula 1"],
    "hogar": [" room tour", " ikea", " decoracion", " limpiar", " limpieza", " cleaning", " ducha", " organizar",
              " orden en casa", " home decor", " interiorismo"],
    "animales": [" perrito", " gatito", " grizzly", " cachorro", " mascota", " puppy", " kitten", " gatos", " perros",
                 " oso ", " leon ", " tiburon"],
    "musica": [" piano", " freestyle", " batalla de gallos", " cancion", " album", " concierto", " guitarra",
               " guitar", " cover ", " rapero", " reggaeton", " spotify"],
    "ciencia": [" fisica", " universo", " nasa", " astronomia", " quimica", " biologia", " experimento",
                " cientificos", " scientists", " quantum", " cuantica"],
    "negocios": [" clientes", " agencia", " side hustle", " shopify", " dropshipping", " emprendedor", " emprender",
                 " startup", " founder", " fundador", " ecommerce", " marketing digital"],
    "motivacion": [" disciplina", " mindset", " mentalidad", " motivacion", " motivation", " self improvement"],
    "diseño": [" tipografia", " typography", " figma", " branding", " logo ", " diseno grafico", " graphic design",
               " ui design", " ux design", " web design"],
}

# subcarpetas: palabras de más (se suman a SUB_KW)
SUB_AMPLIA = {
    "fitness_salud/entreno": [" dominada", " pull up", " pullup", " chin up", " barra fija", " calistenia",
                              " calisthenics", " plan de entrenamiento", " hipertrofia", " press banca",
                              " bench press", " gimnasio"],
    "fitness_salud/salud": [" ansiedad", " anxiety", " respiracion", " breathing", " sistema inmune", " immune",
                            " medico", " habitos", " meditacion"],
    "recetas/saludables": [" high protein", " low calorie", " quinoa", " proteica", " sin azucar", " healthy"],
    "recetas/bebidas": [" gin tonic", " vodka", " ron ", " cocktails", " cocteles"],
    "tecnologia/webs": [" cookies del navegador", " navegador", " chrome ", " webs gratis"],
    "tecnologia/gadgets": [" unboxing", " airpods", " lampara", " escritorio", " desk setup"],
    "videojuegos/recomendaciones": [" tienes que jugar", " must play", " que jugar", " juegos de ps5", " breakdown",
                                    " todo lo que sabemos"],
    "videojuegos/trucos": [" trofeos", " trophies", " diamantes", " infinitos", " best deck"],
    "sitios/cafes": [" brunch"],
    "viajes/destinos": [" itinerary", " itinerario", " ruta en coche", " road trip", " roadtrip", " pueblos",
                        " islas", " paisajes", " travel guide", " guia de viaje"],
    "anime/edits": [" animeedit", " amv", " edit "],
    "anime/recomendaciones": [" infravalorad", " tienes que ver", " que ver", " animes que", " anime to watch",
                              " must watch"],
    "pelis_series/series": [" season", " the bear", " miniserie", " miniseries"],
    "finanzas/dinero": [" comisiones", " banco", " ganar pasta", " pasta extra"],
    "finanzas/inversion": [" mercado se desploma", " bolsa de", " la bolsa", " fondo indexado", " index fund"],
    "moda/outfits": [" bolso", " bolsos", " handbag", " model off duty", " looks"],
}

# Palabras de relleno: solo sirven para trocear hashtags y cuentas (#comerenmadrid -> comer en madrid)
RELLENO = ["de", "del", "en", "con", "la", "el", "los", "las", "mi", "tu", "por", "para", "que", "y", "un", "una",
           "the", "and", "of", "in", "my", "to", "for", "with", "by", "best", "top", "new", "life", "daily",
           "official", "club", "world", "time", "day", "night", "love", "good", "real", "just", "all", "your",
           "espana", "spain", "madrid", "barcelona", "london", "paris", "tokyo", "nyc", "edits", "clips", "vibes",
           "page", "show", "news", "tips", "hacks", "lover", "lovers", "addict", "fan", "fans", "mania", "zone",
           "world", "hub", "media", "studio", "studios", "network", "channel", "home", "house", "nation"]

# Contexto: frases que cambian el sentido de una palabra. Se buscan en el texto ya normalizado
# (minúsculas, sin acentos, signos separados por espacios). {carpeta o ruta: puntos de más/menos}
CONTEXTO = [
    (r"\b(ganar|gana|ganas|ganando|mucha|muchisima|una|buena) pasta\b|\bpasta (extra|gansa)\b",
     {"finanzas": 2.5, "finanzas/dinero": 2, "recetas": -2.5, "sitios": -2}),
    (r"\b(pull|chin|muscle) ?ups?\b|\bdominadas?\b|\bbarra fija\b|\bcalist", {"fitness_salud": 2, "fitness_salud/entreno": 2,
                                                                             "sitios": -3, "sitios/bares": -3}),
    (r"\bgato hidraulico\b|\bgato (del|de) coche\b", {"coches": 3, "animales": -3}),
    (r"\bruta en coche\b|\broad ?trip\b|\broadtrip\b", {"viajes": 2, "coches": -2}),
    (r"\bcookies? (del|de tu|de la|of the|in your|en el) (navegador|browser|web|pagina)|\b(acepta|aceptar|accept|borrar|"
     r"borra|clear|delete|bloquear|block) (las |the |all )?cookies\b", {"tecnologia": 3, "tecnologia/webs": 3,
                                                                       "recetas": -3}),
    (r"\b(stock ?market|mercado de valores|wall street|(el|los) mercados? (se desploma|cae|caen|sube|suben|bajista|alcista))\b"
     r"|\bla bolsa (de|cae|sube|se)\b|\bbolsa de (valores|madrid|nueva york|ny)\b", {"finanzas": 2, "finanzas/inversion": 2}),
    (r"\bbols(o|os)\b|\bbolsas? de (mano|loewe|zara|tela)\b", {"moda": 1.5, "finanzas": -1.5}),
    (r"\banime\b|\bmanga\b|\bmanhwa\b", {"anime": 1.5, "pelis_series": -1}),
    (r"\( (19[2-9]\d|20[0-3]\d) \)", {"pelis_series": 1.5}),   # "On Your Mark (1995)": título de peli con año
    (r"\b(modelo|model) de (regresion|machine learning|ml|ia)\b|\bregresion\b", {"finanzas/quant": 1.5}),
    (r"\b(model|modelo|modelos|models) (off ?duty|look|style|outfit)", {"moda": 2, "finanzas": -1}),
    (r"\breceta\b|\brecipe\b", {"sitios": -1.5}),
    (r"\bgin\b", {"recetas/bebidas": 1}),
]

# La cuenta que lo publica: un trozo de su @usuario o nombre ya dice mucho (@dryaneats, @sonypics…)
CUENTA = {
    "pelis_series": ["movie", "film", "cine", "cinema", "pictures", "netflix", "hbo", "scenes", "kino", "letterbox"],
    "anime": ["anime", "otaku", "manga", "amv", "weeb"],
    "humor": ["meme", "humor", "funny", "comedy", "jaja", "risas", "chistes"],
    "recetas": ["recipe", "receta", "cocina", "kitchen", "baking", "bakes", "cooking"],
    "sitios": ["eats", "foodie", "spots", "planesmadrid", "restaurant", "dondecomer"],
    "tecnologia": ["tech", "coding", "programa", "openai", "claude", "chatgpt", "automat", "nocode"],
    "finanzas": ["finanz", "financ", "invest", "invert", "trading", "trader", "wealth", "stocks", "dinero"],
    "videojuegos": ["gaming", "gamer", "minecraft", "fortnite", "clash", "pokemon", "nintendo", "playstation", "xbox"],
    "fitness_salud": ["fitness", "gym", "workout", "calisten", "nutri"],
    "moda": ["fashion", "outfit", "barber", "skincare", "styleinspo"],
    "viajes": ["travel", "viaj", "wander", "nomad"],
    "carrera": ["career", "empleo", "studygram", "studywith"],
    "deportes": ["futbol", "football", "soccer", "sports", "deport"],
    "musica": ["music", "musica", "rapper", "piano"],
    "animales": ["dogs", "perro", "gatos", "pets", "animal", "puppy", "kitten", "mascota", "natgeo"],
    "coches": ["supercar", "carsof", "motorsport", "coches"],
}
PESO_CUENTA = 1.5
BONO_SITIO = 4
# "en Madrid" + comida, sin pinta de receta: es un sitio aunque no traiga la dirección
RECETA = re.compile(r"\b(receta|recetas|recipe|recipes|ingredientes?|ingredients?|paso a paso|step by step|como hacer|"
                    r"how to make|homemade|al horno|en casa|at home)\b")
# ======================================================================================
# El motor (01/10/2026). Antes: buscar trocitos de texto ("blob.count(' bar ')"), así que
# " cook" casaba con "cookies", "etf" con "netflix" y "Ruta en coche" iba a Coches.
# Ahora, como un bibliotecario que lee palabra a palabra:
#   1. normaliza: minúsculas, sin acentos, plural -> singular ("bares" = "bar")
#   2. trocea #hashtags y @cuentas: #PastaRecipe / #pastarecipe -> pasta recipe
#   3. cada palabra clave es una palabra entera (o el principio de una, si es larga)
#   4. puntúa por sitio: un hashtag o el nombre de la cuenta pesan más que los subtítulos
#   5. reglas de contexto para las palabras con dos sentidos ("ganar pasta", "gato hidráulico")
#   6. umbral y desempate fijos: mismo texto, mismas carpetas, siempre
# La medida, antes y después, en docs/diseno.md («Ordenar sin IA») y tests/test_precision.py.
# ======================================================================================
import unicodedata  # noqa: E402
from functools import lru_cache  # noqa: E402
from collections import Counter  # noqa: E402

# peso de cada sitio del guardado (medido en tools/medir.py, mitad "dev")
PESO = {"cap": 1.0, "tag": 1.5, "user": 1.0, "tr": 0.6}
TOPE = 2          # una palabra repetida cuenta como mucho 2 veces por sitio
UMBRAL = 1.0      # menos puntos que esto -> "otros"
PESO_SUB_EN_CARPETA = 0.5   # las palabras de una subcarpeta también empujan a su carpeta

_TOK = re.compile(r"[^\W_]+|[^\w\s]")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_TAG = re.compile(r"[#@]([\w.]+)")


def _norm(s):
    """minúsculas y sin acentos (ñ -> n): "Diseño Café" -> "diseno cafe"."""
    s = unicodedata.normalize("NFKD", (s or "").replace("️", "")).lower()
    return "".join(c for c in s if not unicodedata.combining(c))


@lru_cache(maxsize=50000)
def _raiz(w):
    """plural -> singular, solo si el singular es una palabra del diccionario:
    bares -> bar, restaurantes -> restaurante, stories -> story, canciones -> cancion.
    Así "care" no se vuelve "car" ni "sales" "sal" (no se inventa ninguna raíz)."""
    if len(w) > 3 and w[-1] == "s" and w.isalpha():
        for c in ((w[:-3] + "y") if w.endswith("ies") else "", w[:-1], w[:-2] if w.endswith("es") else ""):
            if c and c in _VOCAB:
                return c
    return w


class _Termino:
    """Una palabra clave ya preparada. Convención de las listas (la de rules.py):
    " foo " palabra entera; " foo" principio de palabra; "foo" en cualquier sitio.
    Con palabras cortas (< 5 letras) "principio" y "cualquier sitio" pasan a palabra
    entera: " cook" ya no es "cookies" ni "etf" es "netflix". La palabra entera se
    compara en singular (_raiz); el principio y "dentro", con la palabra tal cual."""
    __slots__ = ("raw", "toks", "modo")

    def __init__(self, kw):
        self.raw = tuple(_TOK.findall(_norm(kw)))
        self.toks = tuple(_raiz(t) for t in self.raw)
        ini, fin = kw.startswith(" "), kw.endswith(" ")
        largo = len(self.raw[-1]) >= 5 if self.raw else False
        if fin or not largo:
            self.modo = "exacta"
        elif not ini and len(self.raw) == 1:
            self.modo = "dentro"
        else:
            self.modo = "principio"


def _vocabulario(listas):
    v = set()
    for kws in listas:
        for kw in kws:
            for t in _TOK.findall(_norm(kw)):
                if t.isalpha() and len(t) >= 2:
                    v.add(t)
    return v


def _trocear(w, vocab):
    """#pastarecipe -> ["pasta", "recipe"] con el vocabulario de las carpetas; [] si no sale limpio."""
    n = len(w)
    if n < 6 or n > 40 or not w.isalpha():
        return []
    best = [None] * (n + 1)
    best[0] = (0.0, [])
    for i in range(n):
        if best[i] is None:
            continue
        c, parts = best[i]
        nxt = (c + 1.5, parts + [(w[i], False)])
        if best[i + 1] is None or nxt[0] < best[i + 1][0]:
            best[i + 1] = nxt
        for j in range(i + 2, min(n, i + 20) + 1):
            sub = w[i:j]
            if sub in vocab or (sub[-1] == "s" and sub[:-1] in vocab):
                nxt = (c + 1.0, parts + [(sub, True)])
                if best[j] is None or nxt[0] < best[j][0]:
                    best[j] = nxt
    parts = best[n][1]
    desconocidas = sum(len(p) for p, ok in parts if not ok)
    conocidas = [p for p, ok in parts if ok]
    if len(conocidas) < 2 or desconocidas > n * 0.25:
        return []
    # con letras sueltas sin reconocer, las piezas de 2 letras ("ai" en "d-ai-ly") no valen
    return [p for p, ok in parts if ok and (len(p) > 2 or not desconocidas)]


def _piezas(nombre, vocab):
    """Un #hashtag o @cuenta: sus trozos (camelCase, _, ., números) y, si van pegados, troceados."""
    out = []
    for trozo in re.split(r"[_.\s]+", _CAMEL.sub(" ", nombre or "")):
        t = _norm(trozo)
        if not t:
            continue
        out.append(t)
        if t not in vocab:
            out.extend(_trocear(t, vocab))
    return out


def _cuenta(blob, kws):
    """El conteo viejo por trocitos de texto: solo lo usa sitios.py para su propia señal."""
    return sum(blob.count(k) for k in kws)


# ---------- el índice: todas las palabras clave preparadas una vez, al importar ----------
def _listas():
    """[(etiqueta, palabras)]: "recetas" para la carpeta, "recetas/postres" para la subcarpeta."""
    out = []
    for cat, kws in rules.KEYWORDS.items():
        out.append((RENOMBRA.get(cat, cat), [ARREGLA.get(k, k) for k in kws if k not in QUITA]))
    for cat, kws in list(EXTRA.items()) + list(AMPLIA.items()):
        out.append((cat, kws))
    for ruta, kws in list(SUB_KW.items()) + list(SUB_AMPLIA.items()):
        out.append((ruta, [k for k in kws if k not in QUITA]))
    return out


def _indice():
    terms, duenos, visto = [], [], {}
    for etiqueta, kws in _listas():
        for kw in kws:
            t = _Termino(kw)
            if not t.toks:
                continue
            k = (t.toks if t.modo == "exacta" else t.raw, t.modo)
            if k not in visto:
                visto[k] = len(terms)
                terms.append(t)
                duenos.append([])
            tid = visto[k]
            if etiqueta not in duenos[tid]:
                duenos[tid].append(etiqueta)
    debiles = {" ".join(_TOK.findall(_norm(x))) for x in DEBILES}
    peso = [0.5 if " ".join(t.raw) in debiles else 1.0 for t in terms]
    exacta, principio, dentro, frase = {}, {}, [], {}
    for tid, t in enumerate(terms):
        if len(t.toks) > 1:
            frase.setdefault(t.toks[0], []).append(tid)
        elif t.modo == "exacta":
            exacta.setdefault(t.toks[0], []).append(tid)
        elif t.modo == "principio":
            principio.setdefault(t.raw[0][:3], []).append(tid)
        else:
            dentro.append(tid)
    return terms, duenos, peso, exacta, principio, dentro, frase


def _aciertos(raw):
    """{término: veces} en una lista de palabras normalizadas (sin pasar a singular)."""
    hits = Counter()
    toks = [_raiz(w) for w in raw]
    for i, w in enumerate(toks):
        for tid in _EXACTA.get(w, ()):
            hits[tid] += 1
        for tid in _PRINCIPIO.get(raw[i][:3], ()):
            if raw[i].startswith(_TERMS[tid].raw[0]):
                hits[tid] += 1
        for tid in _FRASE.get(w, ()):
            t = _TERMS[tid]
            k = len(t.toks)
            if i + k > len(toks) or any(toks[i + j] != t.toks[j] for j in range(1, k - 1)):
                continue
            if toks[i + k - 1] == t.toks[-1] or (t.modo != "exacta" and raw[i + k - 1].startswith(t.raw[-1])):
                hits[tid] += 1
    if _DENTRO and raw:
        junto = " ".join(raw)
        for tid in _DENTRO:
            n = junto.count(_TERMS[tid].raw[0])
            if n:
                hits[tid] += n
    return hits


def _campos(caption, transcript="", username="", fullname=""):
    """Las palabras de cada sitio del guardado, ya normalizadas."""
    caption = caption or ""
    tags = []
    for m in _TAG.finditer(caption):
        tags.extend(_piezas(m.group(1), _VOCAB))
        tags.append("|")   # que una frase no salte de un hashtag al siguiente
    user = _piezas(username, _VOCAB)
    for w in _TOK.findall(_norm(fullname)):
        user.append(w)
        if w.isalpha() and w not in _VOCAB:
            user.extend(_trocear(w, _VOCAB))
    return {"cap": _TOK.findall(_norm(_TAG.sub(" ", caption))), "tag": tags, "user": user,
            "tr": _TOK.findall(_norm(transcript))}


def puntos(caption, transcript="", username="", fullname=""):
    """(carpetas, subcarpetas): {"recetas": 3.0}, {"recetas/postres": 2.0}."""
    top, sub = Counter(), Counter()
    for campo, toks in _campos(caption, transcript, username, fullname).items():
        for tid, n in _aciertos(toks).items():
            w = PESO[campo] * min(n, TOPE) * _PESO_T[tid]
            for lab in _DUENOS[tid]:
                if "/" in lab:
                    sub[lab] += w
                    top[lab.split("/")[0]] += w * PESO_SUB_EN_CARPETA
                else:
                    top[lab] += w
    texto = " ".join(_TOK.findall(_norm(f"{caption} {transcript}")))
    for rx, ajustes in _CONTEXTO:
        if rx.search(texto):
            for lab, d in ajustes.items():
                (sub if "/" in lab else top)[lab] += d
    cuenta = re.sub(r"[^a-z0-9]", "", _norm(f"{username} {fullname}"))
    if cuenta:
        for cat, pistas in CUENTA.items():
            if any(p in cuenta for p in pistas):
                top[cat] += PESO_CUENTA
    return {k: v for k, v in top.items() if v > 0}, {k: v for k, v in sub.items() if v > 0}


def _elige_sub(top, sub):
    if top not in SUB:
        return top
    best, score = None, 0
    for s in SUB[top]:
        n = sub.get(f"{top}/{s}", 0)
        if n > score:
            best, score = s, n
    return f"{top}/{best or POR_DEFECTO[top]}"


def subcarpeta(top, texto):
    """La subcarpeta de `top` según un texto (sitios.py la usa con la descripción)."""
    return _elige_sub(top, puntos(texto)[1])


def rutas(caption, transcript="", username="", fullname="", hay_sitio=False):
    """(rutas, ciudad). hay_sitio: sitios.py encontró un sitio con nombre en la descripción."""
    p, sub = puntos(caption, transcript, username, fullname)
    fuerte = bool(SITIO_FUERTE.search(caption or "")) or hay_sitio
    if fuerte:
        p["sitios"] = p.get("sitios", 0) + BONO_SITIO
    elif "sitios" in p and (RECETA.search(_norm(f"{caption} {transcript}")) or not ciudad(caption)):
        # sin un sitio concreto ni una ciudad, "comer" o "bar" no bastan: mejor viajes/recetas/lo que sea
        p["sitios"] = p["sitios"] * 0.5
    orden = sorted(((c, n) for c, n in p.items() if n >= UMBRAL and c in CARPETAS),
                   key=lambda x: (-x[1], CARPETAS.index(x[0])))   # empate: el orden fijo de CARPETAS
    if not orden:
        return ["otros"], ""
    top, n1 = orden[0]
    elegidas = [top] + [c for c, n in orden[1:3] if n >= 2 and n >= 0.5 * n1 and c != "otros"]
    out = []
    for c in elegidas:
        r = _elige_sub(c, sub)
        if r not in out:
            out.append(r)
    ci = ciudad(caption) if any(r.startswith("sitios/") for r in out) else ""
    return out[:3], ci


_VOCAB = _vocabulario([kws for _, kws in _listas()] + [RELLENO])
_TERMS, _DUENOS, _PESO_T, _EXACTA, _PRINCIPIO, _DENTRO, _FRASE = _indice()
_CONTEXTO = [(re.compile(rx), aj) for rx, aj in CONTEXTO]


# ======================================================================================
# Carpetas a mano (01/10/2026): la persona mete un vídeo en una carpeta que existe o en una
# nueva que nombra ella. db.py las guarda aparte (tabla `manual`) y mandan sobre las reglas.
# El nombre lo escribe una persona y acaba en HTML (data-cat="..." en la web), así que solo
# pasan letras, números, espacios, emojis y - . , — nada de comillas, < > & / : ni nombres
# que en JavaScript ya son otra cosa ("constructor", "__proto__"…).
# ======================================================================================
NOMBRES = {
    "sitios": "Sitios", "viajes": "Viajes", "recetas": "Recetas", "pelis_series": "Pelis y series", "anime": "Anime",
    "tecnologia": "Tecnología", "finanzas": "Finanzas", "carrera": "Carrera y estudios", "videojuegos": "Videojuegos",
    "moda": "Moda y cuidado", "fitness_salud": "Fitness y salud", "humor": "Humor", "musica": "Música",
    "ciencia": "Ciencia y curiosidades", "negocios": "Negocios", "coches": "Coches y motor", "diseño": "Diseño",
    "deportes": "Deportes", "hogar": "Hogar y DIY", "motivacion": "Motivación", "animales": "Animales", "otros": "Otros",
    # subcarpetas (los mismos nombres que la web, app.js SUBS)
    "asiatico": "Asiático", "italiano": "Italiano", "hamburguesas": "Hamburguesas", "espanola": "Española y tapas",
    "restaurantes": "Otros restaurantes", "bares": "Bares y copas", "cafes": "Cafés y dulces", "hoteles": "Hoteles",
    "museos": "Museos y cultura", "planes": "Planes y ocio", "naturaleza": "Naturaleza y escapadas",
    "tiendas": "Tiendas", "destinos": "Destinos", "trucos": "Trucos", "platos": "Platos", "postres": "Postres",
    "saludables": "Saludables", "rapidas": "Rápidas", "bebidas": "Bebidas", "comedia": "Comedia", "accion": "Acción",
    "drama": "Drama", "terror": "Terror", "scifi": "Ciencia ficción", "animacion": "Animación", "series": "Series",
    "recomendaciones": "Recomendaciones", "explicaciones": "Explicaciones", "escenas": "Escenas", "edits": "Edits",
    "ia": "IA y herramientas", "ia_noticias": "Noticias de IA", "asistentes": "ChatGPT y Claude",
    "programacion": "Programación", "automatizaciones": "Automatizaciones", "prompts": "Prompts",
    "webs": "Webs y apps útiles", "apps": "Apps", "gadgets": "Gadgets", "inversion": "Inversión", "trading": "Trading",
    "dinero": "Dinero y ahorro", "quant": "Quant", "practicas": "Prácticas y CV", "estudio": "Técnicas de estudio",
    "universidad": "Universidad", "outfits": "Outfits", "cuidado": "Cuidado personal", "entreno": "Entreno",
    "salud": "Salud", "memes": "Memes", "sketches": "Sketches", "clips": "Clips",
}
RESERVADAS = {"todo", "ideas", "__proto__", "constructor", "prototype", "hasownproperty", "isprototypeof",
              "propertyisenumerable", "tostring", "tolocalestring", "valueof", "__definegetter__", "__definesetter__",
              "__lookupgetter__", "__lookupsetter__", "length", "name"}
MAX_NOMBRE = 40
MAX_RUTAS = 10


def _letra_ok(c):
    cat = unicodedata.category(c)
    return cat[0] in "LNM" or cat == "So" or c in " -.,‍️"


def nombre_carpeta(nombre, claves=()):
    """El nombre que escribe la persona, limpio, o None si no vale. Si es una de `claves` escrita
    a mano ("Recetas", "pelis y series"), devuelve esa clave ("recetas", "pelis_series")."""
    if not isinstance(nombre, str):
        return None
    n = " ".join(nombre.split())
    if not n or len(n) > MAX_NOMBRE or not all(_letra_ok(c) for c in n) or n.lower() in RESERVADAS:
        return None
    k = _norm(n)
    for clave in claves:
        if k in (_norm(clave), _norm(clave).replace("_", " "), _norm(NOMBRES.get(clave, clave))):
            return clave
    return n


def limpia_ruta(r):
    """"Recetas/Postres" -> "recetas/postres"; "Regalos 🎁" -> "Regalos 🎁"; None si no vale."""
    if not isinstance(r, str) or len(r) > 2 * MAX_NOMBRE + 1:
        return None
    partes = r.split("/")
    if not 1 <= len(partes) <= 2:
        return None
    top = nombre_carpeta(partes[0], CARPETAS)
    if top is None or len(partes) == 1:
        return top
    sub = nombre_carpeta(partes[1], SUB.get(top, ()))
    return f"{top}/{sub}" if sub else None


def ruta_valida(r):
    """¿Vale tal cual como carpeta de un guardado? (las del árbol o nombres limpios ya normalizados)"""
    return r in VALIDAS or (isinstance(r, str) and limpia_ruta(r) == r)
