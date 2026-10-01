#!/usr/bin/env python3
"""Titulo + categoria SIN inteligencia artificial: solo palabras clave.

Pensado para ser la base de una futura app que no dependa de ningun modelo.
Cuando no hay confianza suficiente (texto insuficiente o ninguna categoria
encaja), devuelve title=None para que quien llame decida si usa IA como
plan B (ver ig.py: _gemini_titulo, con tope de gasto).
"""
import re

# Espacio delante = principio de palabra (" anime" casa con "#animeedit",
# porque los signos se cambian por espacio, ver SEP_RE); espacio detras =
# palabra entera. Sin espacios = en cualquier sitio (tambien dentro del
# @usuario: "movie" casa con @themoviesfeeds). Empate: gana la que va antes.
# Desde "anime" hacia abajo: categorias nuevas (25/09/2026) para vaciar "otros".
KEYWORDS = {
    "tecnologia": ["claude", "gemini", "gpt", "openai", "chatgpt", "llm", " ia ", " ai ",
                   "mcp", " api", "github", "coding", "programming", "programacion",
                   "agente de ia", "ai agent", "prompt", "python", "javascript", "app gratis",
                   "software", "plugin", " script", "automatiz", "workflow", "vibe coding",
                   "vibecoding", "open source", "codigo abierto", " token", " tech ",
                   " techtok", " technology", " tecnologia", " tecnología", " iphone", " ipad",
                   " macbook", " mac mini", " macmini", " android", " ios ", " windows",
                   " pc ", " ordenador", " laptop", " excel ", " google sheets",
                   " googlesheets", " spreadsheet", " powerpoint", " notion", " gadget",
                   " informatica", " informática", " inteligencia artificial", " app ",
                   " apps ", " aplicación", " aplicacion", " website", " página web",
                   " pagina web", " airpods", " microsoft", " sideload", " nvidia", " robot",
                   " webdev", " dji", " drone", " dron ", " smart glasses", " rayban meta",
                   " raybanmeta", " google forms"],
    "finanzas": ["invert", "trading", "stock", "s&p", "sp500", "etf", " mercado", " acciones",
                 "cartera", "portfolio", "quant", "hedge fund", "bolsa", "cripto", "bitcoin",
                 "dividend", "moving average", "media movil", "wall street", "hedge",
                 " invest ", " investing", " investment", " investor", " dinero", " ahorr",
                 " wealth", " millonario", " millionaire", " impuestos", " inflación",
                 " inflacion", " inflation", " economía", " economia", " economy"],
    "carrera": ["internship", "pasantia", "pasantía", "practica", "prácticas", "resume",
                "curriculum", "currículum", " cv ", "linkedin", "entrevista", "interview",
                " job ", "empleo", "hiring", "recruiter", "goldman sachs", "jp morgan",
                "banca de inversion", "graduate program"],
    "recetas": ["receta", "recipe", "cocina", " cook", " food", "comida", " plato ",
                "ingrediente", " chef ", "horno", "pasta con", "postre", "bizcocho",
                " cocktail", " cóctel", " coctel", " desayuno", " breakfast", " merienda", " merendar", " tarta",
                " cheesecake", " yummy", " cake "],
    "viajes": ["viaje", "travel", " vuelo", "flight", " hotel", "vacation", "vacaciones",
               "turismo", "destino", "aeropuerto", "itinerary", "itinerario", "skiplagged",
               " ibiza", " mallorca", " marbella", " yacht", " playa", " beach", " trip ",
               " roadtrip", " road trip", " tourist", " turista", " japan ", " japón",
               " italy", " italia ", " escapada", " crucero", " cruise", " airbnb", " ryanair",
               " interrail", " paisaje", " island", " isla ", " malta", " mountain",
               " montaña", " hike", " hiking", " bucketlist", " bucket list", " places"],
    "pelis_series": ["pelicula", "película", "movie", "film", " serie", "series ", "netflix",
                     "trailer", " actor ", "actriz", " cine ", "cinema", " cinephile", " hbo",
                     " prime video", " hulu", " tv show", " tvshow", " temporada", " episodio",
                     " escena", " scene", " letterboxd", " imdb", " oscar", " hollywood",
                     " marvel", " spiderman", " spider-man", " batman", " star wars",
                     " harry potter", " harrypotter", " cartoon", " south park", " southpark",
                     " family guy", " familyguy", " simpson", " kdrama", " tarantino", " edit",
                     " disney", " pixar", " dreamworks", " warner", " xmen", " x-men",
                     " starwars", " episode", " snowfall", " dexter", " stifler",
                     " american pie", " americanpie", " entourage", " mentalist",
                     " sexandthecity", " sex and the city", " cobra kai", " cobrakai",
                     " avatar", " grease", " james bond", " jamesbond", " primevideo",
                     " theboys", " invincible", " sitcom", " sonic"],
    "fitness_salud": [" gym ", "fitness", "workout", "entrenamiento", " dieta", " diet ",
                      " salud", " health", "ejercicio", "calorias", "calorías", "muscle",
                      " alergia", " allergy", " allergies", " nutrition", " nutricion",
                      " protein", " proteína", " yoga", " pilates", " dermatitis", " posture",
                      " postura", " dermatolog", " adhd", " tdah"],
    "diseño": [" design", "diseño", " ui ", " ux ", "figma", " css ", "tailwind", "layout",
               "tipografia", "tipografía", "branding", " logo ", "web design", "glassmorphism",
               "neomorphism", "aesthetic", " webdesign"],
    "negocios": ["business", "negocio", "startup", " empresa", "revenue", "ingresos",
                 "monetiz", "marketing", " ventas", " sales ", "ecommerce", "shopify",
                 "agencia", " cliente", " client ", "founder", "fundador", " emprend",
                 " entrepreneur", " dropshipping", " side hustle", " sidehustle"],
    "humor": [" meme", " joke", " broma", "gracioso", " funny", " lol ", "relatable", "comedy",
              " humor", " comedia", " jaja", " prank", " chiste", " sketch", " standup",
              " stand up", " monólogo", " monologo", " parodia", " parody", " cringe",
              " cuñad", " troll"],
    "anime": [" anime", " аниме", "アニメ", " manga", " manhwa", " otaku", " weeb",
              " crunchyroll", " one piece", " onepiece", " naruto", " jujutsu", " jjk",
              " demon slayer", " demonslayer", " kimetsu", " dragon ball", " dragonball",
              " goku", " luffy", " solo leveling", " sololeveling", " hunter x hunter",
              " hunterxhunter", " hxh", " attack on titan", " shingeki", " isekai", " shonen",
              " chainsaw man", " my hero academia", " myheroacademia", " frieren", " ghibli",
              " miyazaki", " cosplay"],
    "videojuegos": [" gaming", " gamer", " videojuego", " video game", " videogame",
                    " pokemon", " pokémon", " pikachu", " nintendo", " playstation", " ps5",
                    " ps4", " ps2", " xbox", " fortnite", " gta", " minecraft",
                    " clash of clans", " clashofclans", " clash royale", " fifa", " eafc",
                    " league of legends", " valorant", " call of duty", " warzone", " codm",
                    " twitch", " streamer", " zelda", " super mario", " mario kart", " roblox",
                    " gameplay", " speedrun", " romhack", " nuzlocke", " 3ds", " game boy",
                    " gameboy", " elden ring", " skyrim", " the sims", " consola", " halo ",
                    " clashroyale", " supercell", " steam ", " games", " brawl",
                    " juegos de pc"],
    "musica": [" music", " música", " song", " canción", " cancion", " rap ", " rapero",
               " rapper", " trap ", " hip hop", " hiphop", " dj ", " djs ", " techno",
               " housemusic", " techhouse", " rave", " concierto", " concert", " album",
               " álbum", " spotify", " remix", " freestyle", " fms", " reggaeton", " cantante",
               " singer", " guitar", " piano", " karaoke", " playlist", " vinilo", " vinyl",
               " beatbox", " batalla de gallos", " redbullbatalla", " lyrics"],
    "deportes": [" futbol", " fútbol", " football", " soccer", " nba", " baloncesto",
                 " basket", " f1 ", " formula1", " formula 1", " fórmula 1", " tenis",
                 " tennis", " real madrid", " realmadrid", " barça", " fc barcelona",
                 " atleti", " messi", " ronaldo", " champions league", " laliga", " la liga",
                 " premier league", " wwe", " ufc", " boxeo", " boxing", " mma ", " padel",
                 " pádel", " world cup", " mundial", " nfl", " golf", " ciclismo", " cycling",
                 " rugby", " sports", " deporte", " golazo", " wrestl", " celtics", " lakers"],
    "moda": [" moda", " fashion", " outfit", " ootd", " streetwear", " ropa", " zara", " haul",
             " zapatillas", " menswear", " mensfashion", " mensstyle", " menstyle",
             " old money", " oldmoney", " grwm", " louis vuitton", " louisvuitton", " gucci",
             " prada", " chanel", " massimo dutti", " massimodutti", " vinted", " taobao",
             " joyas", " jewelry", " jewellery", " accesorios", " accessories", " perfume",
             " fragrance", " fragancia", " skincare", " maquillaje", " makeup", " cabello",
             " haircut", " corte de pelo", " barber", " peluquer", " minoxidil", " manicura",
             " camiseta", " hoodie", " sudadera", " styleinspo", " estilismo", " rolex",
             " watches", " reloj", " nike", " adidas", " airmax", " sephora", " wishlist",
             " moodboard", " cosmetic", " shoe", " zapato", " sneaker", " scalpers",
             " pandabuy", " wallet", " cardholder", " jacket", " chaqueta", " glowup",
             " jawline", " metgala", " met gala"],
    "animales": [" animal", " perro", " perrit", " dog ", " dogs", " doggo", " puppy",
                 " puppies", " cachorr", " gato", " gatit", " cat ", " cats ", " kitten",
                 " mascota", " pet ", " pets ", " wildlife", " wolf", " bird", " pájaro",
                 " pajaro", " caballo", " horse", " natgeo", " hamster", " conejo", " bunny",
                 " bunnies", " tortuga", " turtle", " shark", " tiburón", " tiburon", " lion ",
                 " león", " tiger", " tigre", " elephant", " elefante", " monkey",
                 " veterinari", " golden retriever", " goldenretriever", " peludit"],
    "planes": [" restaurant", " donde comer", " dondecomer", " comerenmadrid", " cenar",
               " brunch", " merienda", " merendar", " planes", " planazo", " que hacer", " qué hacer", " quehacer",
               " madrid", " terraza", " rooftop", " tapas", " discoteca", " nightclub",
               " nueva apertura", " sitios", " hamburgues", " burger", " sushi"],
    "ciencia": [" ciencia", " science", " scientist", " experiment", " fisica", " física",
                " physics", " quimica", " química", " chemistry", " biolog", " history",
                " historia de", " nasa", " universo", " universe", " planeta", " planet ",
                " astronom", " sabías que", " sabias que", " did you know", " curiosidad",
                " fun fact", " dato curioso", " datos curiosos", " matemátic", " matematic",
                " math "],
    "estudios": [" estudiar", " study", " examen", " exam ", " exams", " essay", " college",
                 " universidad", " university", " uni ", " apuntes", " ivy league",
                 " ivyleague", " harvard", " stanford", " selectividad", " deberes",
                 " homework", " student", " estudiante", " profesor", " teacher", " school",
                 " colegio", " instituto", " highschool", " beca ", " becas", " scholarship"],
    "coches": [" coche", " car ", " cars ", " bmw", " porsche", " mercedes", " ferrari",
               " lamborghini", " mclaren", " audi ", " tesla", " mini cooper", " minicooper",
               " supercar", " motor ", " moto ", " motos ", " motorbike", " motorcycle",
               " carmods", " jdm", " drift", " conducir", " peugeot", " fiat ", " carplay",
               " launch control", " carsoftiktok"],
    "hogar": [" interior design", " interiordesign", " interiorismo", " decor", " homedecor",
              " apartment", " piso ", " ikea", " mueble", " furniture", " sofa ", " sofá",
              " limpieza", " cleaning", " bathroom", " shower", " ducha", " diy ",
              " manualidades", " bricolaje", " plantas", " plants", " jardín", " jardin",
              " garden", " renterfriendly", " room tour", " roomtour", " lámpara", " lampara",
              " candle", " lego", " bonsai", " herramientas", " tools "],
    "motivacion": [" motivation", " motivación", " motivacion", " mindset", " mentalidad",
                   " discipline", " disciplina", " self improvement", " selfimprovement",
                   " success", " éxito", " stoic", " estoic", " life advice", " lifeadvice",
                   " life lessons", " lifelessons", " wisdom", " sabiduría", " productivity",
                   " productividad", " hábitos", " habitos", " habits", " desarrollo personal",
                   " crecimiento personal"],
}

# Frases de relleno / bait de interaccion que NO aportan nada sobre el
# contenido real del video ("comenta X y te lo mando", "sigueme", "link en
# bio", "espera al final"...) — muy comunes en cuentas de memes/pelis, donde
# el caption suele ser ruido desconectado de lo que se ve.
RUIDO_RE = re.compile(
    r"("
    r"(comment|comenta|coment[ao])\s+[\"'“]?\w+[\"'”]?\s+(and|y)\s+(i('|’)ll|te)\b"
    r"|link (en|in) (la |mi )?bio"
    r"|(sigueme|sígueme|follow (me|for more|us)\b)"
    r"|(guardalo|guárdalo|save (this|it) (for|para))"
    r"|comparte (esto|con)"
    r"|tag (a|to) (a )?friend|etiqueta a (un|una)"
    r"|(doble|double) tap( si)?"
    r"|(like|comenta) si\b"
    r"|wait (for it|till the end|for the end)"
    r"|you (won'?t|wont) believe|no ?vas a creer"
    r"|(parte|part) 2 en (los )?comentarios"
    r"|which one are you"
    r")",
    re.IGNORECASE)
HASHTAG_RE = re.compile(r"#\w+")
MENTION_RE = re.compile(r"@\w+")
URL_RE = re.compile(r"https?://\S+")

# Categorias donde quien escribe el caption suele estar explicando el video
# de verdad (un truco, una app, un movimiento de mercado), no solo
# reaccionando a un clip ajeno — ahi el caption es una fuente de titulo tan
# buena o mejor que la transcripcion.
CAPTION_FIABLE = {"tecnologia", "finanzas", "negocios", "carrera", "diseño"}

# Idiomas cuyo alfabeto NO es latino (cirilico, cjk, arabe...) — si el
# caption esta mayoritariamente en uno de estos alfabetos pero el audio del
# video se transcribio en otro (o al reves), el caption casi seguro no
# describe ESTE video en concreto (es un texto reciclado / copiado).
NO_LATINO_LANGS = {"ja", "ko", "zh", "ru", "ar", "he", "th", "hi", "el", "uk",
                    "fa", "ur", "bn", "ka", "hy", "am", "mr", "ta", "te", "kn",
                    "ml", "si", "my", "km", "lo"}


def _es_ruido(texto_limpio, crudo=""):
    """True si el texto no dice nada real sobre el video: es bait/relleon,
    o (con el crudo) era sobre todo hashtags/menciones tras limpiarlo."""
    if not texto_limpio:
        return True
    if RUIDO_RE.search(texto_limpio):
        return True
    if crudo and len(crudo) > 40 and len(texto_limpio) < 0.3 * len(crudo):
        return True  # la mayoria del caption era #hashtags/@menciones
    return False


def _script_no_latino(texto):
    """Proporcion de caracteres 'raros' (cirilico, cjk, arabe...) en texto."""
    chars = [ch for ch in texto if not ch.isspace() and ch not in ".,;:!?¿¡\"'()-–—…"]
    if len(chars) < 8:
        return 0.0
    raros = sum(1 for ch in chars if ord(ch) > 0x024F)
    return raros / len(chars)


def _idioma_sospechoso(caption_limpio, lang_transcript):
    """True si el alfabeto del caption no encaja con el idioma hablado en el
    video — señal de que el caption es texto reciclado de otro post."""
    if not lang_transcript or not caption_limpio:
        return False
    ratio = _script_no_latino(caption_limpio)
    audio_no_latino = lang_transcript in NO_LATINO_LANGS
    if audio_no_latino and ratio < 0.2:
        return True   # se habla p.ej. japones y el caption es todo latino
    if not audio_no_latino and ratio > 0.3:
        return True   # se habla es/en/... y el caption es otro alfabeto
    return False


# Signos que se cambian por espacio antes de buscar palabras clave: asi
# "#anime", "(movie)" o "@the_filmspoint" casan con " anime", " movie"...
# (antes un hashtag nunca casaba con una palabra con espacio delante).
# El mismo conjunto esta en app/rules.js (SEP): tocar los dos a la vez.
SEP_RE = re.compile(r"[#@.,;:!?¡¿()\[\]{}\"“”«»/|_*~]")


def _blob(texts):
    """Texto en minusculas, signos -> espacio, con espacios en los bordes
    para que los keywords con espacio al principio/final casen."""
    return f" {SEP_RE.sub(' ', ' '.join(t or '' for t in texts).lower())} "


def categorize(*texts):
    """(categoria, score) a partir de cuantas palabras clave de cada categoria
    aparecen en el texto (caption + transcripcion + hashtags)."""
    blob = _blob(texts)
    scores = {}
    for cat, kws in KEYWORDS.items():
        n = sum(blob.count(kw) for kw in kws)
        if n:
            scores[cat] = n
    if not scores:
        return "otros", 0
    cat = max(scores, key=scores.get)
    return cat, scores[cat]


def categorize_multi(*texts, min_hits=2, share=0.4):
    """Todas las categorias que pesan de verdad, de mas a menos: [(cat, score)].
    Una secundaria entra si tiene >= min_hits palabras clave y al menos
    `share` de las que tiene la principal (evita colar una mencion suelta)."""
    blob = _blob(texts)
    scores = {cat: sum(blob.count(kw) for kw in kws) for cat, kws in KEYWORDS.items()}
    scores = sorted(((c, n) for c, n in scores.items() if n), key=lambda x: -x[1])
    if not scores:
        return []
    top = scores[0][1]
    return [scores[0]] + [(c, n) for c, n in scores[1:] if n >= min_hits and n >= share * top]


def _limpiar(caption):
    t = HASHTAG_RE.sub("", caption or "")
    t = MENTION_RE.sub("", t)
    t = URL_RE.sub("", t)
    return " ".join(t.split())


def rule_title(caption, transcript="", username="", lang=""):
    """Titulo + categoria sin IA + si el resultado es "dudoso" (bool).

    Preferencia por defecto: primera frase real de la transcripcion (lo que
    se DICE suele resumir mejor que la descripcion), caption como reserva.
    Excepcion (CAPTION_FIABLE): en tecnologia/finanzas/negocios/carrera/
    diseño el caption suele SER la explicacion del video, asi que si el
    caption de verdad habla del tema (tiene sus propias palabras clave, no
    solo ruido) se prefiere sobre la transcripcion.

    dudoso=True cuando el caption esta en un alfabeto que no encaja con el
    idioma hablado en el video (señal de texto reciclado de otro post) —
    quien llama deberia intentar verificar con IA aunque aqui ya salga un
    titulo (por transcripcion), y si no puede, mejor quedarse con la
    transcripcion que con un caption que no tiene nada que ver.

    Nota: "el caption nombra una serie/persona distinta a la del clip, en el
    mismo idioma" (p.ej. un caption de Friends sobre un clip de Mentalist)
    NO se puede distinguir con reglas de palabras clave — el dialogo de una
    escena casi nunca menciona el nombre de su propia serie, asi que
    comprobar "¿el caption nombra algo que no esta en la transcripcion?"
    dispara con clips CORRECTAMENTE etiquetados igual que con los mal
    etiquetados (se probo y se descarto por eso). Eso exige saber de que
    trata el video de verdad, que es tarea de un modelo, no de un diccionario.
    """
    cat, score = categorize(caption, transcript, username)

    limpio_transcript = " ".join((transcript or "").split())
    limpio_caption = _limpiar(caption)

    transcript_ok = len(limpio_transcript) >= 25 and not _es_ruido(limpio_transcript)
    caption_ok = len(limpio_caption) >= 25 and not _es_ruido(limpio_caption, caption or "")

    dudoso = caption_ok and _idioma_sospechoso(limpio_caption, lang)

    fuente = ""
    if cat in CAPTION_FIABLE and caption_ok and not dudoso and categorize(limpio_caption)[1] > 0:
        fuente = limpio_caption
    elif transcript_ok:
        fuente = limpio_transcript
    elif caption_ok and not dudoso:
        fuente = limpio_caption

    if not fuente:
        # sin texto real que resumir (todo hashtags/bait/caption dudoso sin
        # transcripcion de apoyo) — sin frames no hay forma de saber de que
        # va sin adivinar de verdad.
        return None, cat, dudoso

    # primera "frase" (hasta el primer punto/exclamacion/interrogacion largo,
    # o si no hay, corta a 100 caracteres por palabra completa)
    m = re.search(r"^(.{20,140}?[.!?])(\s|$)", fuente)
    title = m.group(1).strip() if m else fuente[:100].rsplit(" ", 1)[0]
    return title, cat, dudoso


def write_js_data(path):
    """Las mismas reglas para app/rules.js (el movil las aplica sin el Mac):
    una sola lista de palabras clave, la de aqui."""
    import json
    data = {"kw": KEYWORDS, "fiable": sorted(CAPTION_FIABLE), "ruido": RUIDO_RE.pattern,
            "sep": SEP_RE.pattern}
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    import ig
    c = ig.db()
    rows = c.execute("SELECT * FROM posts WHERE title IS NULL OR title=''").fetchall()
    print(f"{len(rows)} posts sin titulo. Probando reglas (sin tocar la base)...")
    resueltos, dudosos = 0, 0
    for r in rows[:2000]:
        tr = c.execute("SELECT text, lang FROM transcripts WHERE code=?", (r["code"],)).fetchone()
        title, cat, dudoso = rule_title(r["caption"], tr[0] if tr else "", r["username"],
                                         tr[1] if tr else "")
        if title:
            resueltos += 1
        if dudoso:
            dudosos += 1
    print(f"Reglas resolverian {resueltos}/{len(rows)} sin IA "
          f"({resueltos/max(len(rows),1)*100:.0f}%), {dudosos} marcados dudosos "
          f"para verificar con IA.")
