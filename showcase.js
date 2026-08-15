const config = window.AGENT_PORTFOLIO_CONFIG || {};
const key = document.body.dataset.showcase;
const serviceUrl = config[`${key}Url`];
const repositoryUrl = config[`${key}RepositoryUrl`];

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
if (serviceUrl && frame) {
  frame.src = serviceUrl;
  offline?.remove();
} else if (frame) {
  frame.remove();
}
