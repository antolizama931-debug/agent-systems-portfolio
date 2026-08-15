const config = window.AGENT_PORTFOLIO_CONFIG || {};

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

const projects = {
  opspilot: config.opspilotUrl,
  reliability: config.reliabilityUrl,
};

Object.entries(projects).forEach(([name, url]) => {
  document.querySelectorAll(`[data-status="${name}"]`).forEach((label) => {
    label.textContent = url ? "ONLINE" : "READY TO DEPLOY";
  });
  document.querySelectorAll(`[data-status-dot="${name}"]`).forEach((dot) => {
    dot.classList.toggle("offline", !url);
  });
});

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add("visible"));
}, { threshold: 0.12 });

document.querySelectorAll(".project-card, .principle-grid article, .section-head").forEach((item) => observer.observe(item));
