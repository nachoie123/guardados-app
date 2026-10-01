"""Conjunto de prueba etiquetado A MANO para las carpetas sin IA (carpetas.py).

Captions inventados (ninguno es de Nacho), ES y EN, con trampas a propósito:
"bar" de dominadas vs bar de copas, "pasta" dinero vs comida, recetas que nombran
una ciudad, hashtags pegados (#pastarecipe), MAYÚSCULAS, sin acentos, emojis…

Cada caso: (rutas buenas, caption, @usuario, subtítulos). La primera ruta es la
esperada; las demás separadas por "|" también se dan por buenas (cuando dos
subcarpetas son igual de defendibles). Etiquetado antes de tocar carpetas.py.

  python3 tests/test_precision.py     # tabla de precisión y cobertura
"""
CASOS = [
    # ---------------- sitios (un sitio concreto que se puede visitar)
    ("sitios/asiatico", "El mejor ramen de Madrid 🍜📍 Calle de San Bernardo 21. Ticket medio 18€", "comeconjuan", ""),
    ("sitios/asiatico", "🍣🍣🔥 omakase de 12 pases 📍 @kabuki_madrid", "foodiesmad", ""),
    ("sitios/asiatico", "Best dim sum in London 📍 Chinatown, Gerrard St 22", "londoneats", ""),
    ("sitios/italiano", "#nycfood #bestpizza 📍 Joe's Pizza, 7 Carmine St", "nyc.bites", ""),
    ("sitios/italiano", "Probamos la carbonara más famosa de Roma 📍 Da Enzo al 29, Via dei Vascellari 29", "viajarcomiendo", ""),
    ("sitios/hamburguesas", "SMASH BURGER DE 10 📍 Calle Ponzano 34, Madrid #burger", "madridfoodies", ""),
    ("sitios/hamburguesas", "Los mejores tacos al pastor de Madrid están aquí 📍 Taquería Pastor, Calle Hortaleza 12", "tacoslover", ""),
    ("sitios/espanola", "Bravas y croquetas de toda la vida 📍 Bar Docamar, Calle Alcalá 337", "tapeandomadrid", ""),
    ("sitios/espanola", "Menú del día por 14€ con cocido 📍 Casa Carola, Calle Padilla 54", "comerbarato", ""),
    ("sitios/bares", "El mejor bar de copas de Malasaña 🍸 📍 Calle del Pez 12", "nochesmadrid", ""),
    ("sitios/bares", "Rooftop con vistas a la Gran Vía 📍 Azotea del Círculo, Calle Alcalá 42", "planesmadrid", ""),
    ("sitios/bares", "Speakeasy escondido detrás de una lavandería 📍 Calle Echegaray 8", "secretmadrid", ""),
    ("sitios/cafes", "Specialty coffee y el mejor croissant de Madrid ☕️ 📍 Calle Fuencarral 70", "cafesdemadrid", ""),
    ("sitios/cafes", "Brunch top en Chamberí ✅ 📍 C/ del Conde Peñalver, 64", "brunchmadrid", ""),
    ("sitios/hoteles", "Hotel boutique en Mallorca con piscina infinita 📍 Calle Sant Miquel 10, Palma", "hotelesbonitos", ""),
    ("sitios/museos", "Exposición gratis de Sorolla 📍 Museo Sorolla, Paseo del General Martínez Campos 37", "culturamadrid", ""),
    ("sitios/planes", "Plan para este finde: mercadillo vintage + concierto 📍 Matadero Madrid, Paseo de la Chopera 14", "planesfinde", ""),
    ("sitios/planes", "Escape room de terror que da miedo de verdad 📍 Calle Atocha 30", "planesmadrid", ""),
    ("sitios/naturaleza", "Ruta de senderismo con cascada a 1h de Madrid 📍 Las Chorreras, 19275 Somolinos", "rutasnaturales", ""),
    ("sitios/naturaleza", "Cala escondida de agua turquesa 📍 Cala Macarelleta, Menorca", "islasbaleares", ""),
    ("sitios/tiendas", "Tienda vintage con chaquetas a 10€ 📍 Calle Velarde 13", "thriftmadrid", ""),
    ("sitios/restaurantes|sitios/hamburguesas", "Restaurante mexicano con los mejores tacos de cochinita 📍 Calle Libertad 5", "comeconjuan", ""),
    ("sitios/restaurantes|sitios/espanola", "Steak de wagyu en este asador argentino 📍 Calle Velázquez 20, ticket medio 45€", "carnivoros", ""),
    ("sitios/restaurantes|sitios/espanola", "Cenamos en @casa_lucio_madrid, el sitio de los huevos rotos. Reserva con tiempo.", "madfood", ""),

    # ---------------- recetas (cocinar en casa, aunque nombre una ciudad)
    ("recetas/platos", "Receta del cocido madrileño de mi abuela, como en Madrid", "cocinaabuela", ""),
    ("recetas/platos|recetas/rapidas", "Pasta cremosa de champiñones 🍄 #pastarecipe #dinner", "pastalover", ""),
    ("recetas/platos", "Pollo al horno con patatas, la cena del domingo", "recetasdecasa", ""),
    ("recetas/platos", "La paella valenciana auténtica paso a paso (receta)", "cocinavalencia", ""),
    ("recetas/platos", "Lasagna bolognese from scratch, my nonna's recipe", "italianfoodathome", ""),
    ("recetas/platos", "La ratatouille de la película Ratatouille, paso a paso", "cocinadecine", ""),
    ("recetas/postres", "Tarta de queso al horno, el mejor postre del mundo", "cocinaconana", ""),
    ("recetas/postres", "#cheesecake #dessert New York cheesecake without cracks", "bakewithme", ""),
    ("recetas/postres", "Galletas cookies con chips de chocolate 🍪 receta", "dulcesana", ""),
    ("recetas/postres|recetas/rapidas", "Tiramisú en vaso sin huevo crudo", "postresfaciles", ""),
    ("recetas/saludables", "Bowl de avena proteica para el desayuno, 40g de proteína", "fitrecetas", ""),
    ("recetas/saludables", "Healthy meal prep for the week: high protein, low calorie", "mealprepking", ""),
    ("recetas/saludables", "Ensalada de quinoa y garbanzos, receta saludable", "comersano", ""),
    ("recetas/rapidas", "Cena en 10 minutos con 3 ingredientes en la airfryer", "airfryerrecetas", ""),
    ("recetas/rapidas|recetas/platos", "Quick and easy 15 minute garlic noodles #easyrecipes", "quickeats", ""),
    ("recetas/bebidas", "Gin tonic perfecto en casa: el truco del hielo", "coctelesencasa", ""),
    ("recetas/bebidas", "Matcha latte casero mejor que el de Starbucks", "drinksathome", ""),
    ("recetas/bebidas", "3 cocktails you can make with just vodka #cocktailrecipe", "mixology101", ""),

    # ---------------- viajes
    ("viajes/destinos", "Ruta en coche por la Toscana: 5 días, todos los pueblos", "viajaconmigo", ""),
    ("viajes/destinos", "Japan travel guide: 10 days itinerary Tokyo Kyoto Osaka", "wanderlust", ""),
    ("viajes/destinos", "Islas que tienes que visitar antes de los 30 #bucketlist", "viajeros", ""),
    ("viajes/destinos", "PAISAJES DE ISLANDIA QUE PARECEN DE OTRO PLANETA", "travelvibes", ""),
    ("viajes/trucos", "Cómo volar barato con Ryanair sin pagar maleta", "viajarbarato", ""),
    ("viajes/trucos", "Travel hack: skiplagged and hidden city flights to save money", "travelhacks", ""),
    ("viajes/trucos", "Lo que nadie te cuenta del eSIM para viajar a Estados Unidos", "viajeinteligente", ""),

    # ---------------- pelis y series
    ("pelis_series/terror|pelis_series/recomendaciones", "TOP 5 PELIS DE TERROR QUE NO TE DEJARÁN DORMIR", "cinefilo", ""),
    ("pelis_series/series", "Season 3 of The Bear is out and it's perfect", "tvaddict", ""),
    ("pelis_series/series|pelis_series/explicaciones", "Breaking Bad: la escena del episodio que lo cambió todo", "seriesadictos", ""),
    ("pelis_series/scifi|pelis_series/explicaciones", "Interstellar explained: the tesseract scene", "moviebrain", ""),
    ("pelis_series/accion", "John Wick hallway fight scene in 4K", "actionmovies", ""),
    ("pelis_series/comedia", "Superbad is still the funniest movie ever made", "comedyfilms", ""),
    ("pelis_series/drama", "La escena más triste de la película, imposible no llorar", "cinetriste", ""),
    ("pelis_series/animacion|pelis_series/explicaciones", "Detalles de Toy Story que nunca viste (Pixar)", "pixarfacts", ""),
    ("pelis_series/recomendaciones", "Películas que tienes que ver antes de morir 🎬 #pelis", "quever", ""),
    ("pelis_series/explicaciones", "Did you know? Hidden details in The Wolf of Wall Street you never noticed", "filmfacts", ""),
    ("pelis_series/accion|pelis_series/drama|pelis_series/explicaciones", "The Wolf of Wall Street: la escena del restaurante con Matthew McConaughey", "cineescenas", ""),

    # ---------------- anime
    ("anime/edits", "Gojo edit 🔥 #jjk #animeedit #amv", "editsanime", ""),
    ("anime/recomendaciones", "5 animes infravalorados que tienes que ver", "otakuzone", ""),
    ("anime/explicaciones", "One Piece: la teoría del One Piece explicada", "luffyfan", ""),
    ("anime/escenas", "La mejor escena de Naruto vs Pain", "narutoclips", ""),

    # ---------------- tecnología
    ("tecnologia/asistentes|tecnologia/prompts", "10 comandos de ChatGPT que no conocías", "iaenespanol", ""),
    ("tecnologia/asistentes|tecnologia/programacion", "Claude Code just changed how I build apps", "devtips", ""),
    ("tecnologia/programacion", "Aprende Python en 10 minutos: listas y diccionarios", "programaconmigo", ""),
    ("tecnologia/programacion", "React vs Vue in 2026 for frontend developers", "webdevtips", ""),
    ("tecnologia/automatizaciones", "Automatiza tu email con n8n y un agente de IA", "automatizaciones", ""),
    ("tecnologia/automatizaciones", "I automated my entire workflow with Zapier", "nocodeguy", ""),
    ("tecnologia/prompts", "Copia este prompt para que la IA te escriba el CV", "promptsutiles", ""),
    ("tecnologia/webs", "5 webs gratis que parecen ilegales", "webstiles", ""),
    ("tecnologia/webs", "Cómo borrar las cookies del navegador en Chrome", "trucostech", ""),
    ("tecnologia/apps", "Apps de iPhone que deberías tener instaladas ya", "appsdeldia", ""),
    ("tecnologia/gadgets", "Unboxing de las nuevas AirPods Pro y el MacBook Air", "techreviews", ""),
    ("tecnologia/gadgets", "Mi setup de escritorio 2026: monitor, teclado y lámpara", "desksetup", ""),
    ("tecnologia/ia_noticias", "OpenAI acaba de lanzar un nuevo modelo y es una locura", "noticiasia", ""),
    ("tecnologia/ia", "Herramientas de IA para crear vídeos gratis: HeyGen y ElevenLabs", "aitools", ""),
    ("tecnologia/ia", "AI tools that will save you 10 hours a week", "aiweekly", ""),

    # ---------------- finanzas
    ("finanzas/inversion", "Cómo invertir en un fondo indexado con 50€ al mes", "finanzasparatodos", ""),
    ("finanzas/inversion", "La bolsa de Nueva York cierra en máximos: qué hacer con tus acciones", "bolsahoy", ""),
    ("finanzas/inversion", "El mercado se desploma: ¿vendo mis acciones?", "inversorjoven", ""),
    ("finanzas/trading", "Day trading strategy with candlestick patterns", "tradingpro", ""),
    ("finanzas/dinero|negocios", "Cómo ganar pasta extra cada mes sin dejar tu trabajo", "dinerointeligente", ""),
    ("finanzas/dinero", "Regla 50/30/20 para ahorrar dinero con tu sueldo", "ahorrafacil", ""),
    ("finanzas/dinero", "Comisiones del Banco Santander: cómo no pagarlas", "bancosclaros", ""),
    ("finanzas/quant|tecnologia/programacion", "Modelo de regresión en Python para predecir acciones (backtest)", "quantcode", ""),

    # ---------------- carrera
    ("carrera/practicas", "Interview tips for investment banking internships", "ibcareers", ""),
    ("carrera/practicas", "Cómo hacer un CV que pase el filtro ATS", "empleojoven", ""),
    ("carrera/estudio", "Study with me 4h pomodoro, no music", "studygram", ""),
    ("carrera/estudio", "Técnica para memorizar apuntes en la mitad de tiempo", "estudiamejor", ""),
    ("carrera/universidad", "Cómo entrar en Harvard: lo que buscan en la admisión", "ivyleagueprep", ""),

    # ---------------- videojuegos
    ("videojuegos/trucos", "Best Clash Royale deck to reach 9000 trophies", "clashpro", ""),
    ("videojuegos/trucos", "Truco de Minecraft para tener diamantes infinitos", "minecrafttips", ""),
    ("videojuegos/recomendaciones", "GTA 6 trailer 2 breakdown: todo lo que sabemos", "gamingnews", ""),
    ("videojuegos/recomendaciones", "Juegos de PS5 que tienes que jugar este año", "gamerzone", ""),

    # ---------------- moda
    ("moda/outfits", "Old money outfits para el invierno", "styleinspo", ""),
    ("moda/outfits", "Bolso de Loewe vs bolso de Zara: ¿se nota?", "modaybolsos", ""),
    ("moda/outfits", "Model off-duty looks: jeans y chaqueta de cuero", "streetstyle", ""),
    ("moda/cuidado", "Rutina de skincare para piel grasa", "pielperfecta", ""),
    ("moda/cuidado", "Haircut ideas for men 2026: low taper fade", "barberlife", ""),
    ("moda/cuidado", "Perfumes que huelen caro y cuestan poco", "fraganciasbaratas", ""),

    # ---------------- fitness y salud
    ("fitness_salud/entreno", "Pull ups on the bar: 3 tips to get your first one", "calisthenicsguy", ""),
    ("fitness_salud/entreno", "Rutina de dominadas en barra fija para principiantes", "calistenia", ""),
    ("fitness_salud/entreno", "Plan de entrenamiento de 12 semanas para hipertrofia", "gymcoach", ""),
    ("fitness_salud/entreno", "Press banca: errores que te frenan", "fuerzareal", ""),
    ("fitness_salud/salud", "Cómo dormir mejor: 5 hábitos que dicen los médicos", "saludconciencia", ""),
    ("fitness_salud/salud|recetas/saludables", "Ginger shots para el sistema inmune, cada mañana", "vidasana", ""),
    ("fitness_salud/salud", "Ansiedad: técnica de respiración 4-7-8", "psicologiafacil", ""),

    # ---------------- humor
    ("humor/memes", "POV: tu madre cuando le dices que no tienes hambre 😂", "memesespana", ""),
    ("humor/memes", "me when the wifi drops for 2 seconds lmao", "relatablememes", ""),
    ("humor/sketches", "Tipos de compañeros de piso (sketch) jajaja", "humoristas", ""),
    ("humor/clips", "La broma de la cámara oculta salió fatal 😂", "bromasvirales", ""),

    # ---------------- carpetas sueltas
    ("musica", "La canción del verano en piano 🎹", "pianocovers", ""),
    ("musica", "Freestyle brutal en la batalla de gallos", "rapbattles", ""),
    ("ciencia", "¿Sabías que el universo se expande más rápido de lo que creíamos? Física explicada", "cienciafacil", ""),
    ("negocios", "Cómo conseguí mis primeros 10 clientes para mi agencia de marketing", "emprendedor", ""),
    ("negocios|finanzas/dinero", "Side hustle ideas that make $1000/month with Shopify", "hustleguy", ""),
    ("coches", "Porsche 911 GT3 launch control 🔥 #carsoftiktok", "supercarsdaily", ""),
    ("coches", "Cómo usar el gato hidráulico para cambiar una rueda del coche", "mecanicafacil", ""),
    ("diseño", "Tipografías gratis para tu branding en Figma", "designtips", ""),
    ("deportes", "La copa del rey: resumen de la final y el golazo de Vinicius", "futbolhoy", ""),
    ("deportes", "Highlights NBA: Lakers vs Celtics", "nbaclips", ""),
    ("hogar", "Room tour de mi piso de 40m² decorado con IKEA", "decoracionhogar", ""),
    ("hogar", "Cómo limpiar la ducha sin productos químicos", "limpiezafacil", ""),
    ("motivacion", "Disciplina > motivación. Mindset de los que ganan", "mentalidadfuerte", ""),
    ("animales", "Grizzly bear catches salmon in the river", "natgeowild", ""),
    ("animales", "Mi perrito reaccionando a su nuevo juguete 🐶", "perritosfelices", ""),
    ("animales", "Gatitos recién nacidos durmiendo 😍", "gatosdeinstagram", ""),

    # ---------------- sin texto útil
    ("otros", "😍😍😍", "", ""),
    ("otros", "parte 2 👇", "user12345", ""),

    # ---------------- TikTok: el caption no dice nada, los subtítulos sí
    ("finanzas/inversion", "parte 2 #fyp", "finanzasconpablo",
     "hoy os enseño cómo invertir en un fondo indexado, el S&P 500, con muy poco dinero al mes"),
    ("recetas/postres", "no os lo vais a creer #fyp", "dulcesvirales",
     "vamos a hacer un brownie de chocolate, mezclamos la mantequilla con el azúcar y al horno"),
    ("tecnologia/automatizaciones", "esto me ahorra 3 horas al día", "techconlucia",
     "he creado un flujo en n8n que lee mis correos y con un agente de inteligencia artificial responde solo"),

    # ---------------- señales de la cuenta
    ("recetas/platos|recetas/rapidas", "Dinner in 20 🍋", "recipesbyclara", ""),
    ("anime/edits", "🔥🔥🔥", "animeedits.daily", ""),
    ("videojuegos/trucos|videojuegos/recomendaciones", "esto es increíble 😳", "minecraft.builds", ""),
    ("humor/memes", "😂😂😂", "memes.daily", ""),
]

# Escritos DESPUÉS de afinar carpetas.py y medidos una sola vez, sin tocar nada luego: la
# cifra honesta de lo que no se ha visto (docs/diseno.md, «Ordenar sin IA»).
CASOS_NUEVOS = [
    ("sitios/asiatico", "Los gyozas más jugosos de Barcelona 🥟 📍 Carrer de Girona 41", "bcnfoodie", ""),
    ("sitios/bares", "Vermut y cañas en la terraza más bonita de Lavapiés 📍 Calle Argumosa 9", "madridenterraza", ""),
    ("sitios/cafes|sitios/restaurantes", "Tortitas americanas y café de especialidad 📍 Calle Ibiza 31, Madrid", "desayunosmadrid", ""),
    ("sitios/italiano", "PIZZA NAPOLITANA DE MASA MADRE 🍕 📍 Calle Santa Isabel 5", "pizzalovers", ""),
    ("sitios/naturaleza", "Atardecer en el mirador más bonito de Granada 📍 Mirador de San Nicolás", "andaluciaviva", ""),
    ("sitios/museos", "Entrada gratis los domingos al Museo del Prado 📍 Paseo del Prado s/n", "culturagratis", ""),
    ("recetas/postres", "Flan de huevo de la abuela sin horno 🍮", "recetasdeabuela", ""),
    ("recetas/platos", "Salmon teriyaki bowl with rice, my go-to weeknight dinner", "cookwithkai", ""),
    ("recetas/bebidas", "Limonada de fresa casera para el verano 🍓🍋", "bebidasfrescas", ""),
    ("recetas/saludables|recetas/postres", "Brownie proteico sin azúcar, solo 120 calorías", "fitdulces", ""),
    ("recetas/rapidas|recetas/platos", "Tostadas de aguacate y huevo en 5 minutos", "desayunosrapidos", ""),
    ("viajes/destinos", "Qué ver en Lisboa en 3 días: itinerario completo", "viajerosdelmundo", ""),
    ("viajes/trucos", "Cómo encontrar vuelos baratos con Google Flights", "vuelosbaratos", ""),
    ("pelis_series/terror", "The scariest horror movie scene of the decade 😱", "horrorfans", ""),
    ("pelis_series/series", "Temporada 2 de Wednesday ya en Netflix: lo que tienes que saber", "seriesnetflix", ""),
    ("pelis_series/recomendaciones", "5 películas de Netflix para ver este finde 🍿", "quevernetflix", ""),
    ("anime/edits", "Itachi Uchiha edit 🖤 #naruto #anime #edit", "uchihaedits", ""),
    ("anime/recomendaciones", "Top anime you need to watch if you liked Attack on Titan", "animerecs", ""),
    ("tecnologia/programacion", "Tutorial de SQL para principiantes: SELECT, JOIN y GROUP BY", "aprendesql", ""),
    ("tecnologia/asistentes", "Gemini vs ChatGPT: cuál es mejor para estudiar", "iacomparada", ""),
    ("tecnologia/apps", "La app que uso para organizar mi día en el iPhone", "productividadapps", ""),
    ("tecnologia/automatizaciones", "Este bot de Telegram hace mi trabajo por mí (automatización con Python)", "botsutiles", ""),
    ("finanzas/inversion", "Bitcoin a 100k: ¿es tarde para invertir?", "criptohoy", ""),
    ("finanzas/dinero", "Cómo pagar menos impuestos en la declaración de la renta", "dinerofacil", ""),
    ("carrera/practicas", "How I landed a summer analyst internship at Goldman Sachs", "wallstreetintern", ""),
    ("carrera/estudio", "Cómo estudiar 8 horas sin cansarte: método Feynman", "estudiantesfelices", ""),
    ("videojuegos/trucos", "Fortnite: el truco para ganar todas las partidas", "fortnitepro", ""),
    ("moda/outfits", "Zapatillas que combinan con todo 👟", "sneakerhead", ""),
    ("moda/cuidado", "Cómo arreglarte la barba en casa como un barbero", "barbaperfecta", ""),
    ("fitness_salud/entreno", "Glúteos de acero: rutina de 20 minutos en casa", "fitencasa", ""),
    ("fitness_salud/salud", "Los síntomas de la falta de vitamina D que nadie te cuenta", "medicoexplica", ""),
    ("humor/sketches|fitness_salud/entreno", "Tipos de personas en el gimnasio (sketch) 😂", "humorgym", ""),
    ("musica", "Este remix de reggaeton está sonando en todas las discotecas", "djlatino", ""),
    ("deportes", "El gol de Messi que nadie recuerda ⚽", "futbolmemorable", ""),
    ("coches", "BMW M3 vs Mercedes C63: cuál suena mejor", "cochesdeportivos", ""),
    ("hogar", "Ideas para decorar un salón pequeño con plantas", "decoideas", ""),
    ("animales", "Mi golden retriever aprendiendo a nadar 🐕", "goldenlife", ""),
    ("negocios", "Cómo vender en Amazon FBA siendo estudiante", "emprendejoven", ""),
    ("ciencia", "Experimento de química que puedes hacer en casa 🧪", "cienciaencasa", ""),
    ("motivacion", "Nadie va a venir a salvarte. Disciplina cada día.", "mentalidadganadora", ""),
]
