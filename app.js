const config = window.AGENT_PORTFOLIO_CONFIG || {};

const links = {
  github: config.githubUrl,
  oncall: config.onCallAgentUrl,
  oncallRepo: config.onCallRepositoryUrl,
  mewcode: config.mewCodeAgentUrl,
  mewcodeRepo: config.mewCodeRepositoryUrl,
};

Object.entries(links).forEach(([name, href]) => {
  document.querySelectorAll(`[data-link="${name}"]`).forEach((link) => {
    if (href) {
      link.href = href;
      link.target = "_blank";
      link.rel = "noreferrer";
    } else {
      link.classList.add("disabled");
      link.setAttribute("aria-disabled", "true");
      link.title = "部署完成后开放";
    }
  });
});

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add("visible"));
}, { threshold: 0.12 });

document.querySelectorAll(".project-card, .principle-grid article, .section-head").forEach((item) => observer.observe(item));
