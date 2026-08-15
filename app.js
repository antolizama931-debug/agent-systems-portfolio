(() => {
  const config = window.AGENT_PORTFOLIO_CONFIG || {};

  // Use the HTML data-live-url as a public, cache-resistant fallback. This keeps
  // the navigation truthful even while GitHub Pages is serving an older config.js.
  const cardUrl = (name) => document.querySelector(`[data-project="${name}"]`)?.dataset.liveUrl || "";
  const links = {
    github: config.githubUrl,
    opspilotRepository: config.opspilotRepositoryUrl,
    reliabilityRepository: config.reliabilityRepositoryUrl,
  };

  Object.entries(links).forEach(([name, href]) => {
    document.querySelectorAll(`[data-link="${name}"]`).forEach((link) => {
      if (!href) {
        link.classList.add("disabled");
        link.setAttribute("aria-disabled", "true");
        return;
      }
      link.href = href;
      link.target = "_blank";
      link.rel = "noreferrer";
    });
  });

  ["opspilot", "reliability"].forEach((name) => {
    const url = config[`${name}Url`] || cardUrl(name);
    document.querySelectorAll(`[data-status="${name}"]`).forEach((label) => {
      label.textContent = url ? "ONLINE" : "CONFIGURING";
    });
    document.querySelectorAll(`[data-status-dot="${name}"]`).forEach((dot) => {
      dot.classList.toggle("offline", !url);
    });
  });
})();
