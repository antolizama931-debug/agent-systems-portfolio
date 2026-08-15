(() => {
  const config = window.AGENT_PORTFOLIO_CONFIG || {};
  const body = document.body;
  const key = body.dataset.showcase;
  const serviceUrl = config[`${key}Url`] || body.dataset.liveUrl || "";
  const repositoryUrl = config[`${key}RepositoryUrl`] || "";

  document.querySelectorAll('[data-link="github"]').forEach((link) => {
    link.href = config.githubUrl || "#";
    link.target = "_blank";
    link.rel = "noreferrer";
  });

  document.querySelectorAll('[data-link="repository"]').forEach((link) => {
    if (repositoryUrl) {
      link.href = repositoryUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
    } else {
      link.classList.add("disabled");
      link.setAttribute("aria-disabled", "true");
    }
  });

  document.querySelectorAll('[data-action="open-live"]').forEach((link) => {
    if (serviceUrl) {
      link.href = serviceUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
    } else {
      link.classList.add("disabled");
      link.setAttribute("aria-disabled", "true");
    }
  });

  const frame = document.getElementById("live-frame");
  const offline = document.getElementById("live-offline");
  const state = document.getElementById("live-state");
  const setState = (label, failed = false) => {
    if (!state) return;
    state.classList.toggle("is-error", failed);
    state.querySelector("span").textContent = label;
  };

  if (serviceUrl && frame) {
    // The iframe also has an HTML src fallback so the live demo works if this
    // small enhancement script is delayed or served from cache.
    if (frame.src !== serviceUrl) frame.src = serviceUrl;
    offline?.setAttribute("hidden", "true");
    setState("ONLINE");
    frame.addEventListener("load", () => setState("ONLINE"), { once: true });
    frame.addEventListener("error", () => {
      setState("RETRY IN NEW TAB", true);
      offline?.removeAttribute("hidden");
    }, { once: true });
  } else if (frame) {
    frame.remove();
    offline?.removeAttribute("hidden");
    setState("NOT CONFIGURED", true);
  }
})();
