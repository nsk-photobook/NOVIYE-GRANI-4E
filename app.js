(() => {
  "use strict";

  const CLOUD_BASE = "https://thumb.cloud.mail.ru/weblink/thumb/xw1/YjPB/rkGWDEVGu/";
  const EXTENSIONS = ["JPG", "jpg", "JPEG", "jpeg", "PNG", "png"];

  const remoteUrl = (name, ext = "JPG") =>
    `${CLOUD_BASE}${encodeURIComponent(name)}.${ext}`;

  function connectPhoto(img) {
    const name = img.dataset.photo;
    const shell = img.closest("[data-photo-shell]");
    if (!name || !shell) return;

    let attempt = 0;
    let resolved = false;

    const markLoaded = () => {
      resolved = true;
      shell.classList.remove("failed");
      shell.classList.add("loaded");
      img.dataset.resolvedSrc = img.currentSrc || img.src;
    };

    const tryNext = () => {
      if (resolved) return;
      if (attempt >= EXTENSIONS.length) {
        shell.classList.add("failed");
        const status = shell.querySelector(".photo-status");
        if (status) status.textContent = "Фотография временно недоступна";
        return;
      }
      img.src = remoteUrl(name, EXTENSIONS[attempt++]);
    };

    img.addEventListener("load", markLoaded);
    img.addEventListener("error", tryNext);

    if (img.complete && img.naturalWidth > 0) markLoaded();
    else if (!img.getAttribute("src")) tryNext();
  }

  document.querySelectorAll("img[data-photo]").forEach(connectPhoto);

  const header = document.querySelector("[data-header]");
  const syncHeader = () => header?.classList.toggle("scrolled", window.scrollY > 24);
  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  const menuButton = document.querySelector("[data-menu-button]");
  const mobileMenu = document.querySelector("[data-mobile-menu]");
  menuButton?.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    mobileMenu.hidden = isOpen;
  });
  mobileMenu?.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    mobileMenu.hidden = true;
    menuButton?.setAttribute("aria-expanded", "false");
  }));

  const rail = document.querySelector("[data-photo-rail]");
  const railStep = () => Math.min((rail?.clientWidth || 700) * .82, 680);
  document.querySelector("[data-rail-prev]")?.addEventListener("click", () =>
    rail?.scrollBy({ left: -railStep(), behavior: "smooth" }));
  document.querySelector("[data-rail-next]")?.addEventListener("click", () =>
    rail?.scrollBy({ left: railStep(), behavior: "smooth" }));

  const revealItems = [...document.querySelectorAll(".reveal")];
  if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: .1, rootMargin: "0px 0px -4%" });
    revealItems.forEach(item => observer.observe(item));
  } else {
    revealItems.forEach(item => item.classList.add("visible"));
  }

  const lightbox = document.querySelector("[data-lightbox-dialog]");
  const lightboxImage = lightbox?.querySelector("figure img");
  const lightboxCaption = lightbox?.querySelector("figcaption");
  const cards = [...document.querySelectorAll("[data-lightbox]")];
  let activeIndex = 0;

  const showPhoto = index => {
    if (!lightbox || !lightboxImage || cards.length === 0) return;
    activeIndex = (index + cards.length) % cards.length;
    const card = cards[activeIndex];
    const img = card.querySelector("img[data-photo]");
    if (!img) return;
    lightboxImage.src = img.dataset.resolvedSrc || img.currentSrc || img.src || remoteUrl(img.dataset.photo);
    lightboxImage.alt = img.alt;
    if (lightboxCaption) lightboxCaption.textContent = `4 «Е» · кадр ${String(activeIndex + 1).padStart(2, "0")} · 2026`;
  };

  cards.forEach((card, index) => card.addEventListener("click", () => {
    showPhoto(index);
    if (typeof lightbox?.showModal === "function") lightbox.showModal();
  }));

  document.querySelector("[data-lightbox-close]")?.addEventListener("click", () => lightbox?.close());
  document.querySelector("[data-lightbox-prev]")?.addEventListener("click", () => showPhoto(activeIndex - 1));
  document.querySelector("[data-lightbox-next]")?.addEventListener("click", () => showPhoto(activeIndex + 1));
  lightbox?.addEventListener("click", event => {
    if (event.target === lightbox) lightbox.close();
  });
  document.addEventListener("keydown", event => {
    if (!lightbox?.open) return;
    if (event.key === "ArrowLeft") showPhoto(activeIndex - 1);
    if (event.key === "ArrowRight") showPhoto(activeIndex + 1);
  });
})();
