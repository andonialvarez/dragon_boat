"""Carga contenidos de EJEMPLO para ver la web funcionando.

Todo lo que crea este comando es ficticio (equipos, resultados, noticias,
usuarios...) y queda marcado con `is_sample=True`: la web lo muestra con una
etiqueta «Ejemplo» y se borra de golpe con `python manage.py borrar_datos_ejemplo`.

Las fechas se calculan a partir de hoy, así siempre hay eventos «próximos».
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from competitions.models import Championship, Division, Standing, Team
from core.context_processors import SAMPLE_CACHE_KEY
from core.models import Sport
from events.models import Event
from forum.models import Category, Post, Topic
from news.models import Article, Comment
from reactions.models import Reaction

User = get_user_model()


USERS = [
    # usuario, club, localidad, deporte favorito, bio
    ("redaccion_ejemplo", "", "Bilbao", "dragon-boat", "Cuenta ficticia que firma las noticias de ejemplo."),
    (
        "ejemplo_ane",
        "Dragones Turquesa",
        "Bilbao",
        "dragon-boat",
        "Timonel los sábados, palista el resto de la semana.",
    ),
    (
        "ejemplo_iker",
        "Itsas Lagunak",
        "Getaria",
        "traineras",
        "Remero de banco fijo que se ha enganchado al dragon boat.",
    ),
    ("ejemplo_lucia", "Ola Bermeja", "Sevilla", "dragon-boat", "Aprendiendo a tocar el tambor sin perder el ritmo."),
    ("ejemplo_marta", "Mareas Rosas", "Barcelona", "dragon-boat", "Remo con el equipo BCP desde hace tres temporadas."),
    (
        "ejemplo_pablo",
        "Pala de Fuego",
        "Madrid",
        "piraguismo",
        "Kayakista reconvertido. Busco siempre el agua más cercana.",
    ),
]

TEAMS = [
    # nombre, localidad, zona, país, fundación, deportes, descripción
    (
        "Dragones Turquesa",
        "Bilbao",
        "Bizkaia",
        "España",
        2012,
        ["dragon-boat"],
        "Club ficticio de ejemplo nacido en la ría. Entrena tres días por semana y tiene tripulaciones open, mixta y máster.",
    ),
    (
        "Ola Bermeja",
        "Sevilla",
        "Andalucía",
        "España",
        2015,
        ["dragon-boat"],
        "Equipo ficticio que entrena en el Guadalquivir. Conocido por sus salidas explosivas en 200 metros.",
    ),
    (
        "Escamas de Plata",
        "Valencia",
        "Comunitat Valenciana",
        "España",
        2010,
        ["dragon-boat", "piraguismo"],
        "Club ficticio con larga tradición de piragüismo que se pasó al dragon boat y ya no se bajó del barco.",
    ),
    (
        "Pala de Fuego",
        "Madrid",
        "Comunidad de Madrid",
        "España",
        2018,
        ["dragon-boat"],
        "Equipo ficticio que entrena en un embalse de la sierra. Mezcla de veteranos y palistas recién llegados.",
    ),
    (
        "Tambor del Norte",
        "A Coruña",
        "Galicia",
        "España",
        2016,
        ["dragon-boat"],
        "Equipo ficticio de ejemplo. Su tamborilera es toda una institución en el club.",
    ),
    (
        "Mareas Rosas",
        "Barcelona",
        "Catalunya",
        "España",
        2014,
        ["dragon-boat"],
        "Equipo ficticio de mujeres supervivientes de cáncer de mama (BCP). Reman por la salud y por la vida.",
    ),
    (
        "Brisa de Levante",
        "Alicante",
        "Comunitat Valenciana",
        "España",
        2019,
        ["dragon-boat", "vaa"],
        "Club ficticio que combina dragon boat y canoa polinesia en mar abierto.",
    ),
    (
        "Dragões do Tejo",
        "Lisboa",
        "",
        "Portugal",
        2013,
        ["dragon-boat"],
        "Equipo ficticio de Lisboa, habitual en las regatas internacionales de la península.",
    ),
    (
        "Itsas Lagunak",
        "Getaria",
        "Gipuzkoa",
        "España",
        1990,
        ["traineras"],
        "Club de remo ficticio con trainera, trainerilla y batel. Cantera muy joven.",
    ),
    (
        "Marea Alta",
        "Santander",
        "Cantabria",
        "España",
        1985,
        ["traineras"],
        "Club de remo ficticio de ejemplo con una afición fiel en el puerto.",
    ),
    (
        "Galerna Beltza",
        "Bermeo",
        "Bizkaia",
        "España",
        1978,
        ["traineras"],
        "Club de remo ficticio, especialista en mares movidos.",
    ),
    (
        "Remolino Azul",
        "Gijón",
        "Asturias",
        "España",
        1995,
        ["traineras", "piraguismo"],
        "Club ficticio de remo y piragüismo con mucha vida en el puerto deportivo.",
    ),
]


class Command(BaseCommand):
    help = "Crea contenidos de EJEMPLO (ficticios y marcados) para ver la web en marcha."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Borra los datos de ejemplo existentes y los vuelve a crear."
        )

    def handle(self, *args, **options):
        if options["reset"]:
            call_command("borrar_datos_ejemplo", "--si", stdout=self.stdout)
        elif Article.objects.filter(is_sample=True).exists() or Team.objects.filter(is_sample=True).exists():
            self.stdout.write(self.style.WARNING("Ya hay datos de ejemplo. Usa --reset para recrearlos."))
            return

        with transaction.atomic():
            self.today = timezone.localdate()
            self.now = timezone.now()
            self.sports = {sport.slug: sport for sport in Sport.objects.all()}
            if "dragon-boat" not in self.sports:
                self.stderr.write("Faltan los deportes. Ejecuta antes: python manage.py migrate")
                return
            self.users = self.create_users()
            self.teams = self.create_teams()
            self.championships = self.create_championships()
            self.events = self.create_events()
            self.articles = self.create_articles()
            self.create_comments()
            self.create_forum()
        cache.delete(SAMPLE_CACHE_KEY)
        self.stdout.write(
            self.style.SUCCESS(
                "Datos de ejemplo creados: "
                f"{len(self.teams)} equipos, {len(self.championships)} campeonatos, {len(self.events)} eventos, "
                f"{len(self.articles)} noticias y {Topic.objects.filter(is_sample=True).count()} temas del foro."
            )
        )

    # --- Usuarios ---------------------------------------------------------

    def create_users(self):
        users = {}
        for username, club, city, sport_slug, bio in USERS:
            user, _created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            user.set_unusable_password()
            user.save()
            profile, _created = Profile.objects.get_or_create(user=user)
            profile.club, profile.city, profile.bio = club, city, bio
            profile.favorite_sport = self.sports.get(sport_slug)
            profile.is_sample = True
            profile.save()
            users[username] = user
        return users

    # --- Equipos ----------------------------------------------------------

    def create_teams(self):
        teams = {}
        for name, city, region, country, founded, sports, description in TEAMS:
            team = Team(name=name, city=city, region=region, country=country, founded_year=founded, is_sample=True)
            team.description = description
            team.save()
            team.sports.set([self.sports[slug] for slug in sports if slug in self.sports])
            teams[name] = team
        return teams

    # --- Campeonatos y clasificaciones ------------------------------------

    def create_championships(self):
        year = self.today.year
        db = self.sports["dragon-boat"]
        result = {}

        league = Championship(
            sport=db,
            season=year,
            scope=Championship.Scope.NATIONAL,
            organizer="Organización de ejemplo",
            location="Bilbao · Sevilla · Valencia",
            start_date=self.today - timedelta(days=60),
            end_date=self.today + timedelta(days=40),
            is_featured=True,
            is_sample=True,
        )
        league.name = f"Liga Demo de Dragon Boat {year}"
        league.description = "Liga ficticia de ejemplo en tres jornadas, con categorías de barco grande y pequeño. Sirve para ver cómo se muestran las clasificaciones."
        league.save()
        result["league"] = league

        mixed = Division(championship=league, order=1)
        mixed.name = "Mixto · barco grande (20) · 200 m"
        mixed.notes = "Puntos acumulados tras 2 de 3 jornadas"
        mixed.save()
        for position, (team, points) in enumerate(
            [
                ("Dragones Turquesa", "38"),
                ("Ola Bermeja", "35"),
                ("Escamas de Plata", "31"),
                ("Pala de Fuego", "26"),
                ("Tambor del Norte", "22"),
                ("Brisa de Levante", "19"),
                ("Mareas Rosas", "15"),
                ("Dragões do Tejo", "12"),
            ],
            start=1,
        ):
            Standing.objects.create(division=mixed, team=self.teams[team], position=position, points=Decimal(points))

        small = Division(championship=league, order=2)
        small.name = "Open · barco pequeño (10) · 500 m"
        small.notes = "Final A de la jornada 2"
        small.save()
        for position, (team, time) in enumerate(
            [
                ("Ola Bermeja", "2:11,48"),
                ("Dragones Turquesa", "2:12,05"),
                ("Pala de Fuego", "2:14,90"),
                ("Escamas de Plata", "2:15,32"),
                ("Tambor del Norte", "2:19,77"),
            ],
            start=1,
        ):
            Standing.objects.create(division=small, team=self.teams[team], position=position, result_time=time)

        traineras = Championship(
            sport=self.sports["traineras"],
            season=year,
            scope=Championship.Scope.REGIONAL,
            organizer="Organización de ejemplo",
            location="Costa cantábrica",
            start_date=self.today - timedelta(days=150),
            end_date=self.today - timedelta(days=60),
            is_sample=True,
        )
        traineras.name = f"Trofeo Demo de Traineras {year}"
        traineras.description = (
            "Competición ficticia de ejemplo de banco fijo, con regatas por tandas sobre tres millas náuticas."
        )
        traineras.save()
        result["traineras"] = traineras
        general = Division(championship=traineras, order=1)
        general.name = "Clasificación general"
        general.save()
        for position, (team, points, time) in enumerate(
            [
                ("Itsas Lagunak", "46", ""),
                ("Galerna Beltza", "41", ""),
                ("Marea Alta", "37", ""),
                ("Remolino Azul", "30", ""),
            ],
            start=1,
        ):
            Standing.objects.create(
                division=general, team=self.teams[team], position=position, points=Decimal(points), result_time=time
            )

        winter = Championship(
            sport=db,
            season=(self.today + timedelta(days=100)).year,
            scope=Championship.Scope.NATIONAL,
            organizer="Organización de ejemplo",
            location="Madrid",
            start_date=self.today + timedelta(days=100),
            end_date=self.today + timedelta(days=101),
            is_sample=True,
        )
        winter.name = "Campeonato Demo de Invierno"
        winter.description = "Campeonato ficticio que todavía no se ha disputado: así se ve uno sin resultados."
        winter.save()
        result["winter"] = winter
        return result

    # --- Eventos ----------------------------------------------------------

    def create_events(self):
        d = lambda days: self.today + timedelta(days=days)  # noqa: E731
        t = self.teams
        rows = [
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.LEAGUE,
                "start": d(12),
                "city": "Valencia",
                "region": "Comunitat Valenciana",
                "venue": "Dársena del puerto",
                "distances": "200 m, 500 m",
                "championship": "league",
                "deadline": d(5),
                "participants": [
                    "Dragones Turquesa",
                    "Ola Bermeja",
                    "Escamas de Plata",
                    "Pala de Fuego",
                    "Tambor del Norte",
                    "Brisa de Levante",
                ],
                "title": "Jornada 3 · Liga Demo de Dragon Boat",
                "summary": "Última jornada de la liga de ejemplo: se decide el título del barco grande mixto.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.TRAINING,
                "start": d(19),
                "city": "Bilbao",
                "region": "Bizkaia",
                "venue": "Pantalán de la ría",
                "distances": "",
                "title": "Clinic de tamborileros y timoneles",
                "summary": "Jornada práctica de ejemplo para aprender a marcar el ritmo y gobernar el barco.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.REGATTA,
                "start": d(26),
                "city": "Sevilla",
                "region": "Andalucía",
                "venue": "Río Guadalquivir",
                "distances": "200 m, 2.000 m",
                "participants": ["Ola Bermeja", "Pala de Fuego", "Mareas Rosas", "Dragões do Tejo"],
                "title": "Regata de Otoño de Dragon Boat",
                "summary": "Regata ficticia de ejemplo con sprint de 200 m y persecución de 2.000 m.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.FESTIVAL,
                "start": d(40),
                "end": d(41),
                "city": "Barcelona",
                "region": "Catalunya",
                "venue": "Port Olímpic",
                "distances": "200 m",
                "participants": ["Mareas Rosas", "Escamas de Plata", "Brisa de Levante"],
                "title": "Festival Solidario Dragon Boat Rosa",
                "summary": "Festival ficticio de ejemplo con regatas amistosas y bautizos de agua para todo el público.",
            },
            {
                "sport": "vaa",
                "kind": Event.Kind.CROSSING,
                "start": d(55),
                "city": "Alicante",
                "region": "Comunitat Valenciana",
                "venue": "Playa del Postiguet",
                "distances": "12 km",
                "participants": ["Brisa de Levante"],
                "title": "Travesía Demo de Va'a",
                "summary": "Travesía ficticia en canoa polinesia V6 a lo largo de la costa.",
            },
            {
                "sport": "piraguismo",
                "kind": Event.Kind.REGATTA,
                "start": d(70),
                "city": "Zaragoza",
                "region": "Aragón",
                "venue": "Río Ebro",
                "distances": "8 km",
                "title": "Descenso Demo de Piragüismo",
                "summary": "Descenso ficticio de ejemplo en K1 y K2 abierto a clubes y piragüistas populares.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.CHAMPIONSHIP,
                "start": d(100),
                "end": d(101),
                "city": "Madrid",
                "region": "Comunidad de Madrid",
                "venue": "Embalse de la sierra",
                "distances": "200 m, 500 m, 2.000 m",
                "championship": "winter",
                "title": "Campeonato Demo de Invierno",
                "summary": "Dos días de competición ficticia para cerrar la temporada de ejemplo.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.LEAGUE,
                "start": d(-20),
                "city": "Sevilla",
                "region": "Andalucía",
                "venue": "Río Guadalquivir",
                "distances": "200 m, 500 m",
                "championship": "league",
                "participants": [
                    "Dragones Turquesa",
                    "Ola Bermeja",
                    "Escamas de Plata",
                    "Pala de Fuego",
                    "Tambor del Norte",
                ],
                "title": "Jornada 2 · Liga Demo de Dragon Boat",
                "summary": "Segunda jornada de la liga de ejemplo.",
            },
            {
                "sport": "dragon-boat",
                "kind": Event.Kind.LEAGUE,
                "start": d(-60),
                "city": "Bilbao",
                "region": "Bizkaia",
                "venue": "Ría de Bilbao",
                "distances": "200 m",
                "championship": "league",
                "title": "Jornada 1 · Liga Demo de Dragon Boat",
                "summary": "Primera jornada de la liga de ejemplo.",
            },
            {
                "sport": "traineras",
                "kind": Event.Kind.REGATTA,
                "start": d(-70),
                "city": "Santander",
                "region": "Cantabria",
                "venue": "Bahía de Santander",
                "distances": "3 millas náuticas",
                "championship": "traineras",
                "participants": ["Itsas Lagunak", "Marea Alta", "Galerna Beltza", "Remolino Azul"],
                "title": "Bandera Demo de Traineras",
                "summary": "Regata ficticia de traineras con cuatro tripulaciones en una sola tanda.",
            },
        ]
        events = []
        for row in rows:
            event = Event(
                sport=self.sports[row["sport"]],
                kind=row["kind"],
                start_date=row["start"],
                end_date=row.get("end"),
                city=row["city"],
                region=row["region"],
                venue=row["venue"],
                distances=row["distances"],
                organizer="Organización de ejemplo",
                registration_url="https://example.com/inscripcion" if row["start"] > self.today else "",
                registration_deadline=row.get("deadline"),
                championship=self.championships.get(row.get("championship")),
                is_sample=True,
            )
            event.title = row["title"]
            event.summary = row["summary"]
            event.description = "Evento ficticio creado como dato de ejemplo. Aquí iría el programa, los horarios, las categorías y la información práctica (cómo llegar, aparcamiento, vestuarios...)."
            event.save()
            event.participants.set([t[name] for name in row.get("participants", [])])
            events.append(event)
        self.event_by_title = {event.title: event for event in events}
        return events

    # --- Noticias ---------------------------------------------------------

    def create_articles(self):
        db = self.sports["dragon-boat"]
        editor = self.users["redaccion_ejemplo"]
        h = lambda hours: self.now - timedelta(hours=hours)  # noqa: E731
        A = Article
        articles = []

        def make(
            sport,
            category,
            hours,
            title,
            summary,
            body,
            *,
            author=editor,
            origin=A.Origin.EDITORIAL,
            featured=False,
            event=None,
            championship=None,
        ):
            article = Article(
                sport=sport,
                category=category,
                status=A.Status.PUBLISHED,
                origin=origin,
                published_at=h(hours),
                author=author,
                is_featured=featured,
                related_event=event,
                related_championship=championship,
                is_sample=True,
            )
            article.title = title
            article.summary = summary
            article.body = body
            article.save()
            articles.append(article)
            return article

        make(
            db,
            A.Category.COMPETITION,
            20,
            "Dragones Turquesa lideran la Liga Demo tras la segunda jornada",
            "El equipo bilbaíno suma 38 puntos en barco grande mixto, tres más que Ola Bermeja, a falta de la jornada final en Valencia.",
            "La segunda jornada de la Liga Demo, disputada en el Guadalquivir, dejó la clasificación más apretada que nunca. Dragones Turquesa ganaron la final de 200 metros en barco grande mixto y se colocan líderes con 38 puntos.\n\n"
            "Ola Bermeja, que corría en casa, se impuso en la final de 500 metros en barco pequeño y llegará a Valencia a solo tres puntos. «Nos jugamos todo en la última jornada; el barco está fino», explicaba su timonel al terminar.\n\n"
            "La jornada final se disputará en la dársena del puerto de Valencia. La organización recuerda que el plazo de inscripción cierra una semana antes.",
            featured=True,
            event=self.event_by_title.get("Jornada 2 · Liga Demo de Dragon Boat"),
            championship=self.championships["league"],
        )
        make(
            db,
            A.Category.COMPETITION,
            50,
            "Abiertas las inscripciones para la Jornada 3 en Valencia",
            "Los clubes pueden apuntar ya sus tripulaciones de 10 y 20 palistas para la última cita de la liga de ejemplo.",
            "La organización de la Liga Demo ha abierto el plazo de inscripción para la tercera y última jornada, que se celebrará en la dársena del puerto de Valencia.\n\n"
            "Habrá pruebas de 200 y 500 metros en barco grande y pequeño. Cada club puede inscribir varias tripulaciones, siempre que cada palista compita en una sola por categoría.\n\n"
            "Toda la información y el enlace de inscripción están en la ficha del evento.",
            event=self.event_by_title.get("Jornada 3 · Liga Demo de Dragon Boat"),
            championship=self.championships["league"],
        )
        make(
            db,
            A.Category.INTERVIEW,
            75,
            "Mareas Rosas: remar para recuperar la confianza",
            "Hablamos con una palista del equipo BCP de ejemplo sobre lo que el dragon boat aporta después de un cáncer de mama.",
            "Mareas Rosas es un equipo ficticio de ejemplo, pero representa a muchas tripulaciones reales: mujeres que han pasado por un cáncer de mama y que encontraron en el dragon boat un lugar para recuperar fuerza y confianza.\n\n"
            "«Lo mejor es que nadie rema sola. Cuando el tambor marca el ritmo y veinte palas entran a la vez, te olvidas de todo», cuenta una de sus palistas.\n\n"
            "El equipo participa en festivales y regatas amistosas y anima a cualquier persona interesada a probar un día.",
        )
        make(
            db,
            A.Category.TRAINING,
            120,
            "Cinco claves para sincronizar un barco de 20 palistas",
            "Mirar la pala de delante, escuchar el tambor y respirar juntos: consejos básicos para remar como un solo cuerpo.",
            "1. Mira la pala del palista que tienes delante en tu lado, no el agua. La primera fila (los «marcadores») marca el ritmo para todo el barco.\n\n"
            "2. Entra con la pala a la vez que tu compañero de banco: el ataque (la entrada en el agua) es el momento clave.\n\n"
            "3. Escucha al tamborilero y al timonel. Las órdenes deben ser cortas y claras.\n\n"
            "4. Rota el tronco en lugar de tirar solo con los brazos: es más eficaz y protege los hombros.\n\n"
            "5. Entrena las salidas: los primeros diez golpes deciden muchas regatas de 200 metros.\n\n"
            "(Artículo de ejemplo.)",
        )
        make(
            self.sports["traineras"],
            A.Category.COMPETITION,
            160,
            "Itsas Lagunak se lleva el Trofeo Demo de Traineras",
            "La tripulación de Getaria cierra una temporada de ejemplo impecable con cinco victorias.",
            "Itsas Lagunak, club ficticio de ejemplo, ganó la última regata del Trofeo Demo en la bahía de Santander y se aseguró el título con 46 puntos.\n\n"
            "Galerna Beltza fue segunda en la general y Marea Alta, tercera. Las cuatro tripulaciones disputaron una sola tanda con mar tranquila.",
            event=self.event_by_title.get("Bandera Demo de Traineras"),
            championship=self.championships["traineras"],
        )
        make(
            self.sports["vaa"],
            A.Category.CLUBS,
            200,
            "Brisa de Levante organiza una travesía de va'a abierta a todos",
            "El club de ejemplo pone sus canoas V6 a disposición de quien quiera probar la canoa polinesia.",
            "Brisa de Levante, club ficticio de ejemplo, organiza una travesía de 12 kilómetros en canoa polinesia. No hace falta experiencia: el club pone las canoas, las palas y los chalecos.\n\n"
            "Las plazas son limitadas y se asignarán por orden de inscripción.",
            event=self.event_by_title.get("Travesía Demo de Va'a"),
        )
        make(
            db,
            A.Category.CLUBS,
            260,
            "Nuevo barco para Pala de Fuego gracias a un crowdfunding",
            "Más de 200 personas aportaron para que el equipo de ejemplo estrene un barco grande de competición.",
            "Pala de Fuego, equipo ficticio de ejemplo, ha conseguido financiar un barco de 20 plazas gracias a una campaña de micromecenazgo en la que participaron más de 200 personas.\n\n"
            "El barco se bautizará con la tradicional ceremonia de «pintar el ojo» del dragón antes de su primera regata.\n\n"
            "(Noticia publicada por un usuario de ejemplo para mostrar cómo se ven las publicaciones de la comunidad.)",
            author=self.users["ejemplo_pablo"],
            origin=A.Origin.COMMUNITY,
        )
        make(
            db,
            A.Category.INTERNATIONAL,
            320,
            "Dragões do Tejo invitan a clubes españoles a su regata de primavera",
            "El equipo lisboeta de ejemplo quiere más tripulaciones de la península en su cita anual.",
            "Dragões do Tejo, equipo ficticio de ejemplo, ha enviado una invitación a los clubes españoles para su regata de primavera en el estuario del Tajo.\n\n"
            "La organización ofrecerá alquiler de barcos para los equipos que no puedan desplazar el suyo.",
        )
        return articles

    # --- Comentarios y reacciones ------------------------------------------

    def react(self, obj, pairs):
        content_type = ContentType.objects.get_for_model(obj)
        for username, kind in pairs:
            Reaction.objects.get_or_create(
                user=self.users[username], content_type=content_type, object_id=obj.pk, kind=kind
            )

    def comment(self, article, username, body, hours, parent=None):
        created = self.now - timedelta(hours=hours)
        comment = Comment.objects.create(
            article=article, author=self.users[username], body=body, parent=parent, created_at=created, is_sample=True
        )
        Comment.objects.filter(pk=comment.pk).update(updated_at=created)  # Que no salga como «editado».
        return comment

    def create_comments(self):
        lead, entries, interview = self.articles[0], self.articles[1], self.articles[2]
        c1 = self.comment(
            lead, "ejemplo_ane", "¡Qué jornada! La salida de la final fue de las mejores del año. A por Valencia 💪", 18
        )
        self.comment(
            lead, "ejemplo_lucia", "Felicidades, pero en Valencia os esperamos con el barco afinado 😄", 17, parent=c1
        )
        self.comment(lead, "ejemplo_ane", "¡Así me gusta! Nos vemos en el agua.", 16, parent=c1)
        c2 = self.comment(
            lead,
            "ejemplo_iker",
            "Vengo de traineras y me sorprende lo explosivo que es el 200 m. ¿Cuántos golpes por minuto se dan en una salida?",
            12,
        )
        self.comment(
            lead,
            "ejemplo_marta",
            "En la salida se puede pasar de 100 golpes por minuto; luego se baja a un ritmo de crucero.",
            10,
            parent=c2,
        )
        self.comment(
            entries, "ejemplo_pablo", "¿Se puede inscribir una tripulación mixta con dos palistas de otro club?", 30
        )
        self.comment(interview, "ejemplo_ane", "Qué bonito reportaje. Mareas Rosas son un ejemplo para todos.", 60)

        self.react(
            lead,
            [
                ("ejemplo_ane", "fire"),
                ("ejemplo_lucia", "clap"),
                ("ejemplo_iker", "like"),
                ("ejemplo_marta", "dragon"),
                ("ejemplo_pablo", "fire"),
            ],
        )
        self.react(
            interview,
            [("ejemplo_ane", "love"), ("ejemplo_lucia", "love"), ("ejemplo_iker", "clap"), ("ejemplo_pablo", "love")],
        )
        self.react(entries, [("ejemplo_pablo", "like")])
        self.react(c1, [("ejemplo_lucia", "like"), ("ejemplo_marta", "fire")])
        self.react(c2, [("ejemplo_marta", "like")])

    # --- Foro --------------------------------------------------------------

    def create_forum(self):
        categories = {category.slug: category for category in Category.objects.all()}
        if not categories:
            return
        threads = [
            (
                "dragon-boat",
                "¿Cómo empezar como tamborilero?",
                "ejemplo_lucia",
                96,
                False,
                [
                    (
                        "ejemplo_lucia",
                        "Mi club me ha propuesto ir al tambor en la próxima regata y estoy un poco perdida. ¿Algún consejo para no perder el ritmo y que me entienda todo el barco?",
                    ),
                    (
                        "ejemplo_ane",
                        "Lo más importante es mirar a los marcadores (la primera fila) y seguir su pala, no imponer tú el ritmo. El tambor acompaña.",
                    ),
                    (
                        "ejemplo_marta",
                        "Y practica las órdenes en voz alta en tierra: cortas, claras y siempre las mismas palabras.",
                    ),
                    ("ejemplo_lucia", "¡Gracias a las dos! Probaré en el próximo entrenamiento y os cuento."),
                ],
            ),
            (
                "clubes-y-equipos",
                "Busco equipo de dragon boat en Madrid",
                "ejemplo_pablo",
                70,
                False,
                [
                    (
                        "ejemplo_pablo",
                        "Hola, vengo del kayak y me gustaría probar el dragon boat. ¿Hay algún club por Madrid que acepte gente nueva?",
                    ),
                    (
                        "ejemplo_ane",
                        "Prueba a escribir a los clubes de la sección Equipos de esta web. Casi todos hacen jornadas de puertas abiertas.",
                    ),
                ],
            ),
            (
                "competiciones-y-regatas",
                "Horarios de la Jornada 3 en Valencia",
                "redaccion_ejemplo",
                40,
                True,
                [
                    (
                        "redaccion_ejemplo",
                        "Tema fijado para resolver dudas sobre la jornada de Valencia (evento de ejemplo). Los horarios definitivos se publicarán en la ficha del evento.",
                    ),
                    ("ejemplo_lucia", "¿Habrá zona para dejar los barcos la noche anterior?"),
                ],
            ),
            (
                "material-y-embarcaciones",
                "¿Palas de carbono o de madera para empezar?",
                "ejemplo_iker",
                30,
                False,
                [
                    (
                        "ejemplo_iker",
                        "Me quiero comprar mi primera pala de dragon boat. ¿Merece la pena ir directamente a carbono?",
                    ),
                    (
                        "ejemplo_marta",
                        "Para empezar, una pala homologada de fibra o madera va de sobra. Mira bien la longitud: mejor que te la ajusten en el club.",
                    ),
                    ("ejemplo_pablo", "Coincido. El carbono pesa menos, pero primero hay que pulir la técnica."),
                ],
            ),
            (
                "traineras-y-remo",
                "¿Qué diferencia hay entre trainera, trainerilla y batel?",
                "ejemplo_marta",
                22,
                False,
                [
                    (
                        "ejemplo_marta",
                        "Desde el dragon boat siempre me lío con las embarcaciones de banco fijo. ¿Alguien me lo explica?",
                    ),
                    (
                        "ejemplo_iker",
                        "Es sobre todo el tamaño: la trainera lleva 13 remeros y patrón; la trainerilla, 6 y patrón; y el batel, 4 y patrón.",
                    ),
                ],
            ),
            (
                "charla-general",
                "¡Hola desde Bilbao! Me presento",
                "ejemplo_ane",
                8,
                False,
                [
                    (
                        "ejemplo_ane",
                        "Kaixo! Soy timonel en un club de la ría. Encantada de tener por fin un sitio para hablar de dragon boat.",
                    ),
                    ("ejemplo_iker", "¡Ongi etorri! Nos vemos por el agua."),
                ],
            ),
        ]
        for slug, title, author, hours, pinned, posts in threads:
            category = categories.get(slug) or next(iter(categories.values()))
            start = self.now - timedelta(hours=hours)
            topic = Topic.objects.create(
                category=category,
                title=title,
                author=self.users[author],
                created_at=start,
                last_activity_at=start,
                is_pinned=pinned,
                is_sample=True,
            )
            created = start
            for index, (username, body) in enumerate(posts):
                created = start + timedelta(hours=index * 3)
                post = Post.objects.create(
                    topic=topic, author=self.users[username], body=body, created_at=created, is_sample=True
                )
                Post.objects.filter(pk=post.pk).update(updated_at=created)
                if index == 1:
                    self.react(post, [(posts[0][0], "like")])
            topic.last_activity_at = min(created, self.now)
            topic.save(update_fields=["last_activity_at"])
