(() => {
  const cfg = window.ALBUM_CONFIG || {};
  const photos = Array.isArray(window.ALBUM_PHOTOS) ? window.ALBUM_PHOTOS : [];
  document.title = `${cfg.className || '4 «Е»'} — выпускной альбом ${cfg.year || '2026'}`;
  document.querySelectorAll('.overline span')[0].textContent = cfg.school || 'Школа № 219';
  document.querySelectorAll('.overline span')[1].textContent = cfg.city || 'Новосибирск';
  document.querySelector('.class-stamp b').textContent = cfg.className || '4 «Е»';
  document.querySelector('.class-stamp span').textContent = cfg.year || '2026';
  document.querySelector('.signature').textContent = `${cfg.className || '4 «Е»'} · ${cfg.year || '2026'}`;
  document.getElementById('footerSchool').textContent = `${cfg.school || 'Школа № 219'} · ${cfg.year || '2026'}`;

  const hero = document.getElementById('heroBg');
  const chapter = document.getElementById('chapterPhoto');
  if (photos[0]) hero.style.backgroundImage = `url("${photos[0].full}")`;
  if (photos[4] || photos[0]) chapter.style.backgroundImage = `url("${(photos[4] || photos[0]).full}")`;

  const grid = document.getElementById('photoGrid');
  const empty = document.getElementById('emptyState');
  let visible = [...photos];
  let activeIndex = 0;

  function render(filter='all') {
    visible = filter === 'all' ? [...photos] : photos.filter(p => p.category === filter);
    grid.innerHTML = '';
    empty.hidden = visible.length > 0;
    visible.forEach((p, index) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'photo-card';
      card.dataset.index = index;
      card.setAttribute('aria-label', `Открыть фотографию: ${p.title}`);
      const img = document.createElement('img');
      img.src = p.thumb || p.full;
      img.dataset.full = p.full;
      img.alt = p.alt || p.title || 'Фотография класса';
      img.loading = index < 3 ? 'eager' : 'lazy';
      const label = document.createElement('span'); label.textContent = p.title || `Кадр ${index+1}`;
      card.append(img,label); card.addEventListener('click',()=>openLightbox(index)); grid.append(card);
    });
  }

  document.querySelectorAll('[data-filter]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===btn));
    render(btn.dataset.filter);
  }));

  const dialog = document.getElementById('lightbox');
  const lbImg = document.getElementById('lbImage'); const lbCap = document.getElementById('lbCaption');
  function openLightbox(index){ if(!visible.length) return; activeIndex=index; updateLightbox(); dialog.showModal(); }
  function updateLightbox(){ const p=visible[activeIndex]; lbImg.src=p.full; lbImg.alt=p.alt||p.title||''; lbCap.textContent=p.title||''; }
  function move(step){ activeIndex=(activeIndex+step+visible.length)%visible.length; updateLightbox(); }
  document.querySelector('.lb-close').addEventListener('click',()=>dialog.close());
  document.querySelector('.lb-prev').addEventListener('click',()=>move(-1));
  document.querySelector('.lb-next').addEventListener('click',()=>move(1));
  dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
  document.addEventListener('keydown',e=>{if(!dialog.open)return;if(e.key==='ArrowLeft')move(-1);if(e.key==='ArrowRight')move(1)});
  document.getElementById('themeToggle').addEventListener('click',()=>document.body.classList.toggle('dark'));
  render();
})();
