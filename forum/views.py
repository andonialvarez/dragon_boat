from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Greatest
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from reactions.utils import attach_reactions

from .forms import PostEditForm, PostForm, TopicForm, TopicTitleForm
from .models import POSTS_PER_PAGE, Category, Post, Topic

TOPICS_PER_PAGE = 25
VISIBLE_POSTS = Q(posts__is_hidden=False, posts__is_deleted=False)


def topics_with_stats(queryset):
    """Añade número de respuestas y autor del último mensaje a cada tema."""
    last_post = Post.objects.filter(topic=OuterRef("pk"), is_hidden=False, is_deleted=False).order_by(
        "-created_at", "-id"
    )
    return queryset.select_related("author", "category").annotate(
        post_count=Count("posts", filter=VISIBLE_POSTS),
        reply_count=Greatest(Count("posts", filter=VISIBLE_POSTS) - 1, Value(0)),
        last_author=Subquery(last_post.values("author__username")[:1]),
    )


def forum_index(request):
    last_topic = Topic.objects.filter(category=OuterRef("pk")).order_by("-last_activity_at")
    categories = Category.objects.select_related("sport").annotate(
        topic_count=Count("topics", distinct=True),
        post_count=Count(
            "topics__posts",
            filter=Q(topics__posts__is_hidden=False, topics__posts__is_deleted=False),
            distinct=True,
        ),
        last_topic_title=Subquery(last_topic.values("title")[:1]),
        last_topic_id=Subquery(last_topic.values("id")[:1]),
        last_topic_slug=Subquery(last_topic.values("slug")[:1]),
        last_activity=Subquery(last_topic.values("last_activity_at")[:1]),
    )
    recent_topics = topics_with_stats(Topic.objects.order_by("-last_activity_at"))[:8]
    return render(request, "forum/index.html", {"categories": categories, "recent_topics": recent_topics})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    topics = topics_with_stats(category.topics.all()).order_by("-is_pinned", "-last_activity_at")
    page = Paginator(topics, TOPICS_PER_PAGE).get_page(request.GET.get("pagina"))
    return render(request, "forum/category.html", {"category": category, "page_obj": page, "topics": page.object_list})


def topic_detail(request, pk, slug=None):
    topic = get_object_or_404(Topic.objects.select_related("category", "author"), pk=pk)
    if slug != topic.slug:
        return redirect(topic, permanent=True)

    posts = topic.posts.select_related("author", "author__profile").order_by("created_at", "id")
    page = Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get("pagina"))
    page_posts = list(page.object_list)
    attach_reactions([post for post in page_posts if post.is_visible], request.user)
    first_post_id = posts.values_list("id", flat=True).first()

    return render(
        request,
        "forum/topic.html",
        {
            "topic": topic,
            "category": topic.category,
            "page_obj": page,
            "posts": page_posts,
            "first_post_id": first_post_id,
            "form": PostForm() if request.user.is_authenticated and not topic.is_locked else None,
        },
    )


def new_topic(request, slug):
    category = get_object_or_404(Category, slug=slug)
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    form = TopicForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        now = timezone.now()
        with transaction.atomic():
            topic = Topic.objects.create(
                category=category,
                title=form.cleaned_data["title"],
                author=request.user,
                created_at=now,
                last_activity_at=now,
            )
            Post.objects.create(
                topic=topic,
                author=request.user,
                body=form.cleaned_data["body"],
                image=form.cleaned_data.get("image") or "",
                created_at=now,
            )
        messages.success(request, _("¡Tema publicado!"))
        return redirect(topic)
    return render(request, "forum/topic_form.html", {"category": category, "form": form})


@require_POST
def reply(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if not request.user.is_authenticated:
        return redirect_to_login(f"{topic.get_absolute_url()}#responder")
    if topic.is_locked:
        messages.error(request, _("Este tema está cerrado y no admite respuestas."))
        return redirect(topic)

    form = PostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.topic = topic
        post.author = request.user
        post.save()
        Topic.objects.filter(pk=topic.pk).update(last_activity_at=post.created_at)
        messages.success(request, _("Respuesta publicada."))
        return redirect(post.get_absolute_url())

    # Si hay errores, se vuelve a mostrar la última página con el formulario relleno.
    posts = topic.posts.select_related("author", "author__profile").order_by("created_at", "id")
    paginator = Paginator(posts, POSTS_PER_PAGE)
    page = paginator.get_page(paginator.num_pages)
    page_posts = list(page.object_list)
    attach_reactions([p for p in page_posts if p.is_visible], request.user)
    return render(
        request,
        "forum/topic.html",
        {
            "topic": topic,
            "category": topic.category,
            "page_obj": page,
            "posts": page_posts,
            "first_post_id": posts.values_list("id", flat=True).first(),
            "form": form,
        },
        status=400,
    )


def _own_post_or_403(request, pk):
    post = get_object_or_404(Post.objects.select_related("topic", "topic__category"), pk=pk)
    if post.author_id != request.user.id or post.is_deleted:
        raise PermissionDenied
    if post.is_hidden:
        raise Http404
    return post


@login_required
def edit_post(request, pk):
    post = _own_post_or_403(request, pk)
    is_first = post.is_first
    form = PostEditForm(request.POST or None, request.FILES or None, instance=post)
    title_form = TopicTitleForm(request.POST or None, instance=post.topic, prefix="tema") if is_first else None
    if request.method == "POST" and form.is_valid() and (title_form is None or title_form.is_valid()):
        with transaction.atomic():
            form.save()
            if title_form is not None:
                title_form.save()
        messages.success(request, _("Mensaje actualizado."))
        return redirect(post.get_absolute_url())
    return render(request, "forum/post_form.html", {"form": form, "title_form": title_form, "post": post})


@login_required
def delete_post(request, pk):
    post = _own_post_or_403(request, pk)
    topic = post.topic
    if request.method == "POST":
        others = topic.posts.exclude(pk=post.pk).filter(is_hidden=False, is_deleted=False)
        if post.is_first and not others.exists():
            category = topic.category
            topic.delete()
            messages.success(request, _("Tema borrado."))
            return redirect(category)
        post.is_deleted = True
        post.body = ""
        if post.image:
            post.image.delete(save=False)
        post.image = ""
        post.save()
        messages.success(request, _("Mensaje borrado."))
        return redirect(post.get_absolute_url())
    return render(request, "forum/post_confirm_delete.html", {"post": post, "topic": topic})
