"""Crea los deportes de la web con una descripción general de cada uno.

No son datos de ejemplo: es contenido divulgativo que se puede editar desde el
panel de administración.
"""

from django.db import migrations

TEXT_FIELDS = ("name", "tagline", "description", "crew", "distances", "governing_bodies")

SPORTS = [
    {
        "slug": "dragon-boat",
        "icon": "🐉",
        "color": "#c8102e",
        "propulsion": "pala",
        "is_primary": True,
        "order": 1,
        "es": {
            "name": "Dragon boat",
            "tagline": "El deporte principal de esta web: velocidad, sincronía y espíritu de equipo.",
            "crew": "Barco grande: 20 palistas, tamborilero y timonel. Barco pequeño: 10 palistas, tamborilero y timonel.",
            "distances": "200 m, 500 m, 1.000 m y 2.000 m (persecución)",
            "governing_bodies": "IDBF e ICF (internacional), EDBF (Europa) y Real Federación Española de Piragüismo (España)",
            "description": (
                "El dragon boat nació en el sur de China hace más de 2.000 años y está ligado al Festival del Bote "
                "del Dragón (Duanwu), que se celebra el quinto día del quinto mes del calendario lunar. Según la "
                "tradición, recuerda al poeta Qu Yuan, al que los pescadores intentaron rescatar remando río adentro.\n\n"
                "La embarcación es larga y estrecha, con una cabeza y una cola de dragón decorativas. Los palistas van "
                "sentados por parejas, uno a cada lado, mirando hacia delante, y usan una pala de una sola hoja. En la "
                "proa, el tamborilero marca el ritmo con un tambor; en la popa, el timonel dirige el barco con un remo "
                "largo de gobierno.\n\n"
                "Hoy es un deporte de competición en todo el mundo, con campeonatos nacionales, europeos y mundiales. "
                "Se compite en categorías open, femenina y mixta, y por edades: junior, sub-24, sénior y máster. "
                "Destacan también los equipos de supervivientes de cáncer de mama (BCP, de Breast Cancer Paddlers), "
                "que han convertido el dragon boat en un símbolo de recuperación y apoyo mutuo.\n\n"
                "Lo que hace especial al dragon boat es la sincronía: veinte palas que entran y salen del agua a la "
                "vez. Por eso se dice que es el deporte de equipo por excelencia."
            ),
        },
    },
    {
        "slug": "traineras",
        "icon": "⚓",
        "color": "#0b5394",
        "propulsion": "remo",
        "is_primary": False,
        "order": 2,
        "es": {
            "name": "Traineras",
            "tagline": "Remo de banco fijo en el mar Cantábrico: tradición, puertos llenos y ciabogas.",
            "crew": "13 remeros y un patrón",
            "distances": "3 millas náuticas (5.556 m), con ciabogas",
            "governing_bodies": "Federación Española de Remo y federaciones autonómicas; ligas ACT, ARC y LGT",
            "description": (
                "La trainera es la embarcación de remo de banco fijo más emblemática de la costa cantábrica: País "
                "Vasco, Cantabria, Asturias y Galicia. Su origen está en las lanchas de pesca de bajura que salían a "
                "la mar a remo, y las competiciones nacieron de los desafíos entre pueblos y cofradías por ver quién "
                "llegaba antes a puerto.\n\n"
                "A diferencia del dragon boat, los remeros van de espaldas a la dirección de avance y mueven remos "
                "apoyados en toletes. El patrón, en la popa, dirige la embarcación y marca la estrategia.\n\n"
                "Las regatas se disputan en el mar, normalmente sobre tres millas náuticas con ciabogas (giros "
                "alrededor de una boya). La temporada de verano reúne a miles de aficionados en los puertos, y la "
                "Bandera de La Concha, en San Sebastián, es la regata más célebre.\n\n"
                "También existen embarcaciones menores de banco fijo, como las trainerillas y los bateles."
            ),
        },
    },
    {
        "slug": "piraguismo",
        "icon": "🛶",
        "color": "#d97706",
        "propulsion": "pala",
        "is_primary": False,
        "order": 3,
        "es": {
            "name": "Piragüismo",
            "tagline": "Kayak y canoa en aguas tranquilas, bravas y en el mar.",
            "crew": "Kayak (K1, K2, K4) y canoa (C1, C2, C4)",
            "distances": "Sprint de 200 a 5.000 m; maratón y descensos de larga distancia",
            "governing_bodies": "ICF (internacional) y Real Federación Española de Piragüismo (España)",
            "description": (
                "El piragüismo engloba las disciplinas en las que se impulsa una embarcación ligera con pala, "
                "mirando hacia delante. En el kayak el palista va sentado y usa una pala de doble hoja; en la canoa "
                "va arrodillado y usa una pala de una sola hoja, como en el dragon boat.\n\n"
                "Tiene muchas modalidades: aguas tranquilas (sprint), maratón, slalom y descenso en aguas bravas, "
                "kayak de mar, kayak-polo, estilo libre y paracanoe. El sprint y el slalom forman parte del programa "
                "olímpico.\n\n"
                "En España el piragüismo tiene una enorme tradición, con clubes por todo el país y citas populares "
                "como el Descenso Internacional del Sella, en Asturias. El dragon boat comparte federación con el "
                "piragüismo, así que muchos palistas practican ambas disciplinas."
            ),
        },
    },
    {
        "slug": "remo-olimpico",
        "icon": "🚣",
        "color": "#2e7d32",
        "propulsion": "remo",
        "is_primary": False,
        "order": 4,
        "es": {
            "name": "Remo olímpico",
            "tagline": "Banco móvil, potencia de piernas y la clásica distancia de 2.000 metros.",
            "crew": "De 1 a 8 remeros, con o sin timonel (1x, 2x, 2-, 4x, 4-, 8+)",
            "distances": "2.000 m en aguas tranquilas",
            "governing_bodies": "World Rowing (internacional) y Federación Española de Remo (España)",
            "description": (
                "El remo de banco móvil es el que se ve en los Juegos Olímpicos. Los remeros van de espaldas, "
                "sentados en un carro con ruedas que se desliza sobre unos raíles, de modo que la fuerza de las "
                "piernas se suma a la del tronco y los brazos.\n\n"
                "Hay dos grandes familias: en el remo de pareja (scull) cada remero lleva dos remos, y en el de "
                "punta cada uno lleva uno solo. Las embarcaciones van desde el skiff individual (1x) hasta el ocho "
                "con timonel (8+), el barco más rápido.\n\n"
                "La distancia olímpica es de 2.000 metros en un campo de regatas balizado. También existe el remo de "
                "mar (coastal rowing), que se practica en mar abierto con barcos más anchos y estables."
            ),
        },
    },
    {
        "slug": "vaa",
        "icon": "🌊",
        "color": "#00838f",
        "propulsion": "pala",
        "is_primary": False,
        "order": 5,
        "es": {
            "name": "Va'a (canoa polinesia)",
            "tagline": "La canoa con flotador lateral de la Polinesia, hecha para el mar abierto.",
            "crew": "V1 (individual) y V6 (seis tripulantes)",
            "distances": "Sprint de 250 a 1.500 m y travesías de larga distancia",
            "governing_bodies": "International Va'a Federation (IVF)",
            "description": (
                "La va'a, o canoa polinesia (outrigger), es la embarcación tradicional de Hawái, Tahití y el resto "
                "de la Polinesia. Su rasgo característico es el ama, un flotador lateral unido al casco por unos "
                "brazos (iako) que le da estabilidad en mar abierto.\n\n"
                "Los palistas van mirando hacia delante y usan pala de una sola hoja, con cambios de lado "
                "coordinados. Las modalidades más comunes son la V1, individual, y la V6, con seis tripulantes. Las "
                "regatas de larga distancia en mar abierto son su terreno más espectacular.\n\n"
                "En Europa y en España crece cada año, a menudo de la mano de clubes que también practican dragon "
                "boat o kayak de mar."
            ),
        },
    },
]


def create_sports(apps, schema_editor):
    Sport = apps.get_model("core", "Sport")
    for data in SPORTS:
        values = {key: data[key] for key in ("icon", "color", "propulsion", "is_primary", "order")}
        for field in TEXT_FIELDS:
            values[field] = data["es"][field]
        Sport.objects.update_or_create(slug=data["slug"], defaults=values)


def remove_sports(apps, schema_editor):
    Sport = apps.get_model("core", "Sport")
    Sport.objects.filter(slug__in=[data["slug"] for data in SPORTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(create_sports, remove_sports)]
