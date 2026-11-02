/* Dragon Boat · pequeñas mejoras de interfaz. Todo funciona también sin JavaScript. */
(function () {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : "";
  }

  // Menú en móvil
  const header = document.querySelector(".site-header");
  const toggle = document.querySelector(".nav-toggle");
  if (header && toggle) {
    toggle.addEventListener("click", function () {
      const open = header.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Cerrar el menú de usuario al hacer clic fuera
  document.addEventListener("click", function (event) {
    document.querySelectorAll(".user-menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  // Reacciones sin recargar la página
  document.addEventListener("submit", function (event) {
    const form = event.target.closest(".reaction-form");
    if (!form || !window.fetch) return;
    event.preventDefault();

    const bar = form.closest(".reaction-bar");
    const button = form.querySelector("button");
    button.disabled = true;

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "X-CSRFToken": getCookie("csrftoken") || form.querySelector("[name=csrfmiddlewaretoken]").value,
        "X-Requested-With": "fetch",
        Accept: "application/json",
      },
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { status: response.status, data: data };
        });
      })
      .then(function (result) {
        if (result.status === 401 && result.data.login_url) {
          window.location.href = result.data.login_url;
          return;
        }
        if (result.status !== 200) throw new Error("HTTP " + result.status);
        result.data.reactions.forEach(function (reaction) {
          const btn = bar.querySelector('[data-kind="' + reaction.kind + '"]');
          if (!btn) return;
          btn.setAttribute("aria-pressed", reaction.mine ? "true" : "false");
          btn.dataset.count = reaction.count;
          btn.querySelector(".count").textContent = reaction.count > 0 ? reaction.count : "";
        });
      })
      .catch(function () {
        form.submit(); // Si algo falla, se envía el formulario de la forma clásica.
      })
      .finally(function () {
        button.disabled = false;
      });
  });

  // Mostrar u ocultar el formulario de respuesta de un comentario
  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-reply-to]");
    if (!trigger) return;
    const form = document.getElementById("responder-" + trigger.dataset.replyTo);
    if (!form) return;
    event.preventDefault();
    const hidden = form.hasAttribute("hidden");
    if (hidden) {
      form.removeAttribute("hidden");
      const textarea = form.querySelector("textarea");
      if (textarea) textarea.focus();
    } else {
      form.setAttribute("hidden", "");
    }
    trigger.setAttribute("aria-expanded", hidden ? "true" : "false");
  });

  // Contador de caracteres para áreas de texto con límite
  document.querySelectorAll("textarea[maxlength]").forEach(function (textarea) {
    const max = parseInt(textarea.getAttribute("maxlength"), 10);
    if (!max || max < 500) return;
    const counter = document.createElement("p");
    counter.className = "help";
    counter.setAttribute("aria-live", "polite");
    const update = function () {
      const left = max - textarea.value.length;
      counter.textContent = left < 300 ? left + " caracteres restantes" : "";
    };
    textarea.insertAdjacentElement("afterend", counter);
    textarea.addEventListener("input", update);
    update();
  });

  // En el móvil los filtros se deslizan en horizontal: centra el que está activo.
  document.querySelectorAll(".filters").forEach(function (bar) {
    const active = bar.querySelector("a.active");
    if (!active || bar.scrollWidth <= bar.clientWidth) return;
    const offset = active.getBoundingClientRect().left - bar.getBoundingClientRect().left;
    bar.scrollLeft += offset - (bar.clientWidth - active.offsetWidth) / 2;
  });
})();
