from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from core.utils import safe_next_url
from events.models import Event
from forum.models import Post
from news.models import Article, Comment

from .forms import AccountEmailForm, ProfileForm, SignUpForm
from .models import Profile

User = get_user_model()


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    next_url = safe_next_url(request, request.POST.get("next") or request.GET.get("next"), "")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.UsernameOrEmailBackend")
        messages.success(request, _("¡Bienvenido/a a bordo, %(name)s! Ya puedes comentar y participar en el foro.") % {"name": user.username})
        return redirect(next_url or "home")
    return render(request, "registration/signup.html", {"form": form, "next": next_url})


def profile_detail(request, username):
    person = get_object_or_404(User.objects.select_related("profile", "profile__favorite_sport"), username=username, is_active=True)
    profile, _created = Profile.objects.get_or_create(user=person)
    recent_posts = (
        Post.objects.filter(author=person, is_hidden=False, is_deleted=False)
        .select_related("topic")
        .order_by("-created_at")[:8]
    )
    recent_comments = (
        Comment.objects.filter(author=person, is_hidden=False, is_deleted=False, article__status="publicado")
        .select_related("article")
        .order_by("-created_at")[:8]
    )
    published_articles = Article.objects.published().filter(author=person)
    my_pending = []
    if request.user == person:
        my_pending = list(Article.objects.filter(author=person, status=Article.Status.PENDING)) + list(
            Event.objects.filter(created_by=person, is_published=False)
        )
    return render(
        request,
        "accounts/profile_detail.html",
        {
            "person": person,
            "profile": profile,
            "recent_posts": recent_posts,
            "recent_comments": recent_comments,
            "recent_articles": published_articles[:8],
            "article_count": published_articles.count(),
            "my_pending": my_pending,
            "post_count": Post.objects.filter(author=person, is_hidden=False, is_deleted=False).count(),
            "comment_count": Comment.objects.filter(author=person, is_hidden=False, is_deleted=False).count(),
        },
    )


@login_required
def profile_edit(request):
    profile, _created = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    email_form = AccountEmailForm(request.POST or None, instance=request.user, prefix="cuenta")
    if request.method == "POST" and form.is_valid() and email_form.is_valid():
        with transaction.atomic():
            form.save()
            email_form.save()
        messages.success(request, _("Perfil actualizado."))
        return redirect(profile)
    return render(request, "accounts/profile_edit.html", {"form": form, "email_form": email_form})
