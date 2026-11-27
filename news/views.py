from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from core.community import can_manage, over_daily_limit, requires_approval
from core.models import Sport
from reactions.utils import attach_reactions

from . import buzon
from .forms import ArticleSubmitForm, CommentEditForm, CommentForm, TipForm, TipPublishForm
from .models import Article, Comment, NewsTip


class ArticleListView(ListView):
    template_name = "news/article_list.html"
    context_object_name = "articles"
    paginate_by = 12
    page_kwarg = "pagina"

    def get_queryset(self):
        queryset = Article.objects.published().select_related("sport", "author")
        self.sport = None
        sport_slug = self.request.GET.get("deporte")
        if sport_slug:
            self.sport = get_object_or_404(Sport, slug=sport_slug)
            queryset = queryset.filter(sport=self.sport)
        self.category = self.request.GET.get("seccion", "")
        if self.category in Article.Category.values:
            queryset = queryset.filter(category=self.category)
        else:
            self.category = ""
        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            queryset = queryset.filter(
                Q(title__icontains=self.query) | Q(summary__icontains=self.query) | Q(body__icontains=self.query)
            )
        return queryset.annotate(
            comment_count=Count("comments", filter=Q(comments__is_hidden=False, comments__is_deleted=False))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "current_sport": self.sport,
                "current_category": self.category,
                "categories": Article.Category.choices,
                "query": self.query,
            }
        )
        return context


class ArticleDetailView(DetailView):
    template_name = "news/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        queryset = Article.objects.select_related("sport", "author", "related_event", "related_championship")
        user = self.request.user
        if user.is_staff:
            return queryset  # El equipo editorial puede previsualizar borradores.
        if user.is_authenticated:
            # Cada autor ve sus propias noticias aunque estén pendientes de revisión.
            return queryset.filter(Q(pk__in=Article.objects.published()) | Q(author=user))
        return queryset.published()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        replies = Comment.objects.select_related("author", "author__profile").order_by("created_at")
        comments = list(
            article.comments.filter(parent__isnull=True)
            .select_related("author", "author__profile")
            .prefetch_related(Prefetch("replies", queryset=replies))
        )
        all_comments = comments + [reply for comment in comments for reply in comment.replies.all()]
        attach_reactions([c for c in all_comments if c.is_visible], self.request.user)
        attach_reactions([article], self.request.user)

        related = Article.objects.published().exclude(pk=article.pk).select_related("sport")
        if article.sport_id:
            related = related.filter(sport_id=article.sport_id)

        context.update(
            {
                "comments": comments,
                "comment_count": sum(1 for c in all_comments if c.is_visible),
                "comment_form": CommentForm(),
                "related_articles": related[:3],
                "can_manage": can_manage(self.request.user, article.author_id),
            }
        )
        return context


@require_POST
def add_comment(request, slug):
    article = get_object_or_404(Article.objects.published(), slug=slug)
    if not request.user.is_authenticated:
        return redirect_to_login(f"{article.get_absolute_url()}#comentarios")
    if not article.allow_comments:
        messages.error(request, _("Los comentarios de esta noticia están cerrados."))
        return redirect(article)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article = article
        comment.author = request.user
        parent_id = form.cleaned_data.get("parent_id")
        if parent_id:
            parent = get_object_or_404(Comment, pk=parent_id, article=article)
            # Las respuestas siempre cuelgan del comentario principal (un solo nivel).
            comment.parent = parent.parent or parent
        comment.save()
        messages.success(request, _("Comentario publicado."))
        return redirect(comment.get_absolute_url())

    for error in form.errors.get("body", []):
        messages.error(request, error)
    return redirect(f"{article.get_absolute_url()}#comentarios")


def _own_comment_or_403(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("article"), pk=pk)
    if comment.author_id != request.user.id or comment.is_deleted:
        raise PermissionDenied
    if comment.is_hidden:
        raise Http404
    return comment


@login_required
def edit_comment(request, pk):
    comment = _own_comment_or_403(request, pk)
    form = CommentEditForm(request.POST or None, instance=comment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Comentario actualizado."))
        return redirect(comment.get_absolute_url())
    return render(request, "news/comment_form.html", {"form": form, "comment": comment})


@login_required
def delete_comment(request, pk):
    comment = _own_comment_or_403(request, pk)
    if request.method == "POST":
        url = f"{comment.article.get_absolute_url()}#comentarios"
        if comment.replies.exists():
            # Se conserva el hilo para que las respuestas sigan teniendo sentido.
            comment.is_deleted = True
            comment.body = ""
            comment.save(update_fields=["is_deleted", "body", "updated_at"])
        else:
            comment.delete()
        messages.success(request, _("Comentario borrado."))
        return redirect(url)
    return render(request, "news/comment_confirm_delete.html", {"comment": comment})


@login_required
def article_create(request):
    if over_daily_limit(request.user):
        messages.error(request, _("Has llegado al límite de publicaciones de hoy. Vuelve a intentarlo mañana."))
        return redirect("article_list")
    form = ArticleSubmitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.origin = Article.Origin.EDITORIAL if request.user.is_staff else Article.Origin.COMMUNITY
        pending = requires_approval(request.user)
        article.status = Article.Status.PENDING if pending else Article.Status.PUBLISHED
        article.save()
        if pending:
            messages.success(request, _("¡Gracias! Tu noticia se publicará cuando la revise el equipo."))
        else:
            messages.success(request, _("¡Noticia publicada!"))
        return redirect(article)
    return render(request, "news/article_form.html", {"form": form, "is_new": True})


def _manageable_article(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not can_manage(request.user, article.author_id):
        raise PermissionDenied
    return article


@login_required
def article_edit(request, slug):
    article = _manageable_article(request, slug)
    form = ArticleSubmitForm(request.POST or None, request.FILES or None, instance=article)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Noticia actualizada."))
        return redirect(article)
    return render(request, "news/article_form.html", {"form": form, "article": article, "is_new": False})


@login_required
def article_delete(request, slug):
    article = _manageable_article(request, slug)
    if request.method == "POST":
        article.delete()
        messages.success(request, _("Noticia borrada."))
        return redirect("article_list")
    return render(request, "news/article_confirm_delete.html", {"article": article})


# ---------- Buzón de noticias ----------

TIP_DAILY_LIMIT = 30  # Comprobaciones por persona y día (cada una puede descargar una página).
TIP_DRAFT_DAYS = 7  # Las aportaciones sin terminar se borran pasado este tiempo.


def _tips_today(user):
    return NewsTip.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(hours=24)).count()


def _apply_matches(tip, matches):
    best = matches[0] if matches else None
    if best and best.strong:
        tip.status = NewsTip.Status.DUPLICATE
        tip.match_kind = NewsTip.MatchKind.LINK if best.by_link else NewsTip.MatchKind.TITLE
        tip.match_score = best.score
        tip.article = best.article
    else:
        tip.status = NewsTip.Status.DRAFT
        tip.match_kind = NewsTip.MatchKind.NONE
        tip.match_score = best.score if best else None
        tip.article = None
    if tip.status == NewsTip.Status.DUPLICATE and tip.match_kind == NewsTip.MatchKind.LINK:
        tip.body = ""  # Nada que publicar: no guardamos el texto.


@login_required
def tip_box(request):
    """Buzón: el usuario pega un enlace o sube un documento y la web mira si ya lo tenemos."""
    form = TipForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        if not request.user.is_staff and _tips_today(request.user) >= TIP_DAILY_LIMIT:
            messages.error(request, _("Has mandado muchas cosas al buzón hoy. Vuelve a intentarlo mañana."))
            return redirect("tip_box")
        NewsTip.objects.filter(
            status=NewsTip.Status.DRAFT, created_at__lt=timezone.now() - timedelta(days=TIP_DRAFT_DAYS)
        ).delete()

        tip = NewsTip(user=request.user, comment=form.cleaned_data["comment"])
        if form.cleaned_data["url"]:
            info = buzon.read_link(form.cleaned_data["url"])
            tip.kind = NewsTip.Kind.LINK
            tip.url = (info.canonical_url or info.final_url or info.url)[:600]
            tip.url_keys = " ".join(sorted(info.keys()))[:1900]
            tip.title = info.title
            tip.summary = info.summary
            tip.source_name = info.source_name[:120]
            tip.image_url = info.image_url
            tip.original_published_at = info.published_at
            if not info.fetched:
                messages.info(
                    request,
                    _("No hemos podido abrir esa página, así que no sabemos su título. Escríbelo tú y lo comprobamos."),
                )
        else:
            try:
                info = buzon.read_document(form.cleaned_data["document"])
            except buzon.DocumentError as error:
                form.add_error("document", str(error))
                return render(request, "news/tip_box.html", {"form": form, "tips": _recent_tips(request.user)})
            tip.kind = NewsTip.Kind.DOCUMENT
            tip.file_name = info.file_name
            tip.title = info.title
            tip.summary = info.summary
            tip.body = info.body
        tip.sport = buzon.guess_sport(tip.title, tip.summary, tip.body[:3000], tip.url)
        _apply_matches(tip, buzon.find_matches(tip.title, tip.key_list()))
        tip.save()
        return redirect(tip)
    return render(request, "news/tip_box.html", {"form": form, "tips": _recent_tips(request.user)})


def _recent_tips(user):
    return NewsTip.objects.filter(user=user).select_related("article")[:10]


@login_required
def tip_review(request, pk):
    """Resultado de la comprobación y, si es nueva, revisar y publicar."""
    tip = get_object_or_404(NewsTip.objects.select_related("article", "sport"), pk=pk)
    if tip.user_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied

    initial = {
        "sport": tip.sport_id,
        "category": Article.Category.COMPETITION,
        "title": tip.title,
        "summary": tip.summary,
        "body": tip.body,
        "source_name": tip.source_name,
    }
    form = TipPublishForm(request.POST or None, initial=initial, kind=tip.kind)
    matches = buzon.find_matches(tip.title, tip.key_list(), exclude_pk=tip.article_id) if tip.is_open else []

    if request.method == "POST":
        if not tip.is_open:
            return redirect(tip)
        if over_daily_limit(request.user):
            messages.error(request, _("Has llegado al límite de publicaciones de hoy. Vuelve a intentarlo mañana."))
            return redirect(tip)
        if form.is_valid():
            data = form.cleaned_data
            # Se vuelve a comprobar con el título definitivo, por si lo ha cambiado o alguien se ha adelantado.
            final = buzon.find_matches(data["title"], tip.key_list())
            confirmed = request.POST.get("confirmar") == "1"
            if final and (final[0].by_link or final[0].strong and not confirmed):
                tip.title = data["title"]
                _apply_matches(tip, final)
                tip.save()
                messages.warning(request, _("Esa noticia ya está en la web."))
                return redirect(tip)
            article = _article_from_tip(request, tip, data)
            tip.article = article
            tip.title = article.title
            tip.status = NewsTip.Status.PENDING if article.status == Article.Status.PENDING else NewsTip.Status.PUBLISHED
            tip.body = ""  # El texto ya está en la noticia.
            tip.save()
            if article.status == Article.Status.PENDING:
                messages.success(request, _("¡Gracias! La noticia se publicará cuando la revise el equipo."))
            else:
                messages.success(request, _("¡Gracias! La noticia ya está publicada."))
            return redirect(article)

    return render(request, "news/tip_review.html", {"tip": tip, "form": form, "matches": matches})


def _article_from_tip(request, tip, data):
    is_link = tip.kind == NewsTip.Kind.LINK
    article = Article(
        title=data["title"],
        summary=data["summary"],
        body=data["summary"] if is_link else data["body"],
        sport=data["sport"],
        category=data["category"],
        author=request.user,
        source_name=data["source_name"],
        source_url=tip.url if is_link else "",
        image_url=tip.image_url if is_link else "",
        image_checked_at=timezone.now() if is_link and tip.image_url else None,
    )
    if is_link:
        # Como las que trae la web de otros medios: titular, resumen y enlace al original.
        article.origin = Article.Origin.IMPORTED
        if tip.original_published_at:
            article.published_at = tip.original_published_at
    else:
        article.origin = Article.Origin.EDITORIAL if request.user.is_staff else Article.Origin.COMMUNITY
    article.status = Article.Status.PENDING if requires_approval(request.user) else Article.Status.PUBLISHED
    article.save()
    return article
