'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const icon = (name, className = '') => `<svg class="icon ${className}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const number = value => new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 2}).format(value);
const types = {appartement:'Appartement', maison:'Maison / Villa', terrain:'Terrain', bureau:'Bureau'};
const amenities = ['Balcon','Terrasse','Parking','Jardin','Piscine','Ascenseur','Climatisation','Meublé','Vue mer','Gardien'];
const STORAGE_FAVORITES = 'dar_favorites_v1';
const STORAGE_KEYS = 'dar_owner_keys_v1';

function readStorage(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function saveStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}
const storedFavorites = readStorage(STORAGE_FAVORITES, []);
const storedKeys = readStorage(STORAGE_KEYS, {});
const state = {
  view:'all', transaction:'', propertyType:'', q:'', maxPrice:'', minSurface:'', minRooms:'', sort:'recent',
  items:[], total:0, limit:6, pending:false, controller:null, requestVersion:0,
  favorites:new Set(Array.isArray(storedFavorites) ? storedFavorites.filter(x => typeof x === 'string').slice(0, 200) : []),
  ownerKeys:storedKeys && typeof storedKeys === 'object' && !Array.isArray(storedKeys)
    ? Object.fromEntries(Object.entries(storedKeys).filter(([id, token]) => /^[a-z0-9]{1,32}$/.test(id) && typeof token === 'string' && token.length < 100)) : {},
  currentListing:null, detailVersion:0, editingId:null, photos:[], publishVersion:0, submitting:false, lastCreated:null
};

function toast(message, error = false) {
  const element = document.createElement('div');
  element.className = `toast${error ? ' error' : ''}`;
  element.setAttribute('role', error ? 'alert' : 'status');
  element.innerHTML = icon(error ? 'info' : 'check') + `<span>${escapeHtml(message)}</span>`;
  $('#toast-stack').append(element);
  setTimeout(() => element.remove(), error ? 6500 : 3800);
}

async function request(url, options = {}) {
  let response;
  try { response = await fetch(url, options); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Le serveur est momentanément injoignable. Réessayez dans un instant.');
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    let message = typeof data.detail === 'string' ? data.detail : data.message;
    if (Array.isArray(data.detail)) {
      const translated = data.detail.map(error => {
        if (error.msg.startsWith('Value error, ')) return error.msg.replace('Value error, ', '');
        const name = {title:'Le titre', description:'La description', city:'La ville', price:'Le prix', surface:'La surface', rooms:'Le nombre de pièces', bedrooms:'Le nombre de chambres', contact_name:'Le nom', contact_email:'L’e-mail', contact_phone:'Le téléphone', images:'Les photos'}[error.loc?.at(-1)];
        return name ? `${name} : vérifiez la valeur ou la longueur saisie.` : 'Vérifiez les informations saisies.';
      });
      message = [...new Set(translated)].join('\n');
    }
    throw new Error(message || 'Une erreur est survenue. Veuillez réessayer.');
  }
  return data;
}

function updateScrollLock() { document.body.classList.toggle('modal-open', $$('dialog[open]').length > 0); }
function showDialog(id) {
  const dialog = document.getElementById(id);
  if (!dialog.open) dialog.showModal();
  updateScrollLock();
  dialog.scrollTop = 0;
}
function closeDialog(id) {
  if (id === 'publish-dialog' && state.submitting) { toast('La publication est en cours, encore un instant.'); return; }
  document.getElementById(id).close();
  updateScrollLock();
}

function activeFilterCount() {
  return [state.transaction, state.propertyType, state.q, state.maxPrice, state.minSurface, state.minRooms].filter(Boolean).length;
}
function syncUi() {
  const home = state.view === 'all';
  $('#hero').hidden = !home;
  $('#search-section').hidden = !home;
  $('#publish-banner').hidden = !home;
  $('#ownership-note').hidden = state.view !== 'mine';
  $('#demo-caption').hidden = !home;
  $('#search-q').value = state.q;
  $('#search-type').value = state.propertyType;
  $('#search-budget').value = state.maxPrice;
  $('#filter-surface').value = state.minSurface;
  $('#filter-rooms').value = state.minRooms;
  $('#sort-select').value = state.sort;
  $$('[data-mode]').forEach(button => {
    const active = button.dataset.mode === state.transaction;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  $$('[data-type]').forEach(button => {
    const active = button.dataset.type === state.propertyType;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  $$('[data-nav]').forEach(button => {
    const nav = button.dataset.nav;
    const active = state.view === 'mine' ? nav === 'mine' : home && nav === (state.transaction || 'all');
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  const headings = {
    all:['LA SÉLECTION DAR.', 'Des lieux où se projeter'],
    favorites:['VOS BONNES ADRESSES.', 'Un petit faible pour ces biens'],
    mine:['VOTRE ESPACE DAR.', 'Vos annonces, tout simplement']
  }[state.view];
  $('#results-kicker').textContent = headings[0];
  $('#results-title').innerHTML = `${escapeHtml(headings[1])}<span>.</span>`;
  const count = activeFilterCount();
  $('#filter-count').hidden = count === 0;
  $('#filter-count').textContent = count;
  $('#reset-search').hidden = count === 0;
  syncFavorites();
}

function resetFilters() {
  Object.assign(state, {transaction:'', propertyType:'', q:'', maxPrice:'', minSurface:'', minRooms:'', sort:'recent'});
}
function setView(view, transaction = '', scroll = true) {
  state.view = view;
  resetFilters();
  state.transaction = transaction;
  syncUi();
  return loadListings({scroll});
}

function noPhoto() { return `<div class="card-no-photo">${icon('home')}<span>Un lieu à imaginer.</span></div>`; }
function cardHtml(item) {
  const saved = state.favorites.has(item.id);
  const image = item.images[0] ? `<img class="card-image" src="${escapeHtml(item.images[0])}" alt="${escapeHtml(item.title)}" loading="lazy" width="650" height="410">` : noPhoto();
  const features = [`<span>${icon('area')}${number(item.surface)} m²</span>`];
  if (item.bedrooms > 0) features.push(`<span>${icon('bed')}${item.bedrooms} ch.</span>`);
  if (item.rooms > 0) features.push(`<span>${icon('room')}${item.rooms} pièce${item.rooms > 1 ? 's' : ''}</span>`);
  const id = escapeHtml(item.id);
  return `<article class="listing-card"><div class="card-image-wrap"><a class="card-image-link" href="/?annonce=${id}" data-open="${id}" aria-label="Voir : ${escapeHtml(item.title)}">${image}</a><span class="transaction-badge ${item.transaction_type === 'location' ? 'rent' : ''}">${item.transaction_type === 'vente' ? 'À vendre' : 'À louer'}</span>${item.is_demo ? '<span class="demo-badge">DÉMO</span>' : ''}<button class="favorite-button ${saved ? 'saved' : ''}" data-favorite="${id}" aria-pressed="${saved}" aria-label="${saved ? 'Retirer des favoris' : 'Ajouter aux favoris'}">${icon('heart')}</button></div><div class="card-content"><div class="card-price">${number(item.price)}<span>DT</span>${item.transaction_type === 'location' ? '<small>/ mois</small>' : ''}</div><h3 class="card-title"><a href="/?annonce=${id}" data-open="${id}">${escapeHtml(item.title)}</a></h3><p class="card-location">${icon('pin')}<span>${escapeHtml(item.district ? `${item.district}, ${item.city}` : item.city)}</span></p><div class="card-features">${features.join('')}</div></div></article>`;
}
function skeletons() {
  return Array.from({length:6}, () => '<div class="listing-card skeleton" aria-hidden="true"><div class="skeleton-image"></div><div class="skeleton-body"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div></div></div>').join('');
}
function renderEmpty(error = null) {
  const filtered = activeFilterCount() > 0;
  let title, description, button;
  if (error) {
    title = 'Une petite pause, pas une impasse.';
    description = error;
    button = '<button class="button button-dark" data-retry>Réessayer</button>';
  } else if (filtered) {
    title = 'Le bon lieu se fait encore attendre.';
    description = 'Aucune annonce ne correspond à ces critères. Essayez une autre ville ou un budget plus large.';
    button = '<button class="button button-dark" data-reset>Réinitialiser les filtres</button>';
  } else if (state.view === 'favorites') {
    title = 'Vos coups de cœur commencent ici.';
    description = 'Un bien vous plaît ? Touchez le cœur sur une annonce pour la retrouver facilement.';
    button = '<button class="button button-dark" data-explore>Explorer les annonces</button>';
  } else if (state.view === 'mine') {
    title = 'Et si votre bien était le prochain ?';
    description = 'Vous n’avez pas encore d’annonce dans ce navigateur. Quelques détails, des photos, et c’est parti.';
    button = `<button class="button button-dark" data-publish>Publier mon annonce ${icon('plus')}</button>`;
  } else {
    title = 'La première adresse sera peut-être la vôtre.';
    description = 'Aucun bien n’est encore publié. Soyez le premier à présenter le vôtre.';
    button = '<button class="button button-dark" data-publish>Publier une annonce</button>';
  }
  $('#empty-state').innerHTML = `${icon(error ? 'info' : state.view === 'favorites' ? 'heart' : 'home')}<h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p>${button}`;
  $('#empty-state').hidden = false;
}
function renderListings() {
  $('#listing-grid').innerHTML = state.items.map(cardHtml).join('');
  $('#listing-grid').hidden = state.items.length === 0;
  $('#empty-state').hidden = state.items.length !== 0;
  if (state.items.length === 0) renderEmpty();
  const noun = state.view === 'favorites' ? 'favori' : 'annonce';
  $('#results-summary').innerHTML = `<strong>${state.total} ${noun}${state.total > 1 ? 's' : ''}</strong> ${state.view === 'mine' ? 'dans ce navigateur' : activeFilterCount() ? 'pour votre recherche' : state.view === 'favorites' ? 'à retrouver, à tout moment' : 'pour imaginer la suite'}.`;
  $('#load-more').hidden = state.items.length >= state.total;
  $('#load-more').disabled = false;
}
async function loadListings({append = false, scroll = false} = {}) {
  if (state.controller) state.controller.abort();
  state.controller = new AbortController();
  const version = ++state.requestVersion;
  state.pending = true;
  $('#listing-grid').setAttribute('aria-busy', 'true');
  $('#empty-state').hidden = true;
  $('#load-more').hidden = true;
  if (!append) {
    state.items = [];
    $('#listing-grid').hidden = false;
    $('#listing-grid').innerHTML = skeletons();
    $('#results-summary').textContent = 'Nous cherchons les bonnes adresses…';
  }
  const params = new URLSearchParams({limit:state.limit, offset:append ? state.items.length : 0, sort:state.sort});
  for (const [key, value] of Object.entries({q:state.q, transaction_type:state.transaction, property_type:state.propertyType, max_price:state.maxPrice, min_surface:state.minSurface, min_rooms:state.minRooms})) {
    if (value !== '') params.set(key, value);
  }
  if (state.view === 'favorites') params.set('ids', [...state.favorites].join(','));
  if (state.view === 'mine') params.set('ids', Object.keys(state.ownerKeys).join(','));
  try {
    const page = await request(`/api/listings?${params}`, {signal:state.controller.signal});
    if (version !== state.requestVersion) return;
    state.items = append ? [...state.items, ...page.items] : page.items;
    state.total = page.total;
    renderListings();
  } catch (error) {
    if (error.name === 'AbortError' || version !== state.requestVersion) return;
    if (append) { renderListings(); toast(error.message, true); }
    else { $('#listing-grid').innerHTML = ''; $('#listing-grid').hidden = true; $('#results-summary').textContent = 'Impossible de charger les annonces pour le moment.'; renderEmpty(error.message); }
  } finally {
    if (version === state.requestVersion) {
      state.pending = false;
      $('#listing-grid').setAttribute('aria-busy', 'false');
      if (scroll) $('#annonces').scrollIntoView({behavior:'smooth', block:'start'});
    }
  }
}
async function loadStats() {
  try {
    const stats = await request('/api/stats');
    $('#cities-list').innerHTML = stats.city_names.map(city => `<option value="${escapeHtml(city)}"></option>`).join('');
  } catch { /* La recherche reste utilisable sans suggestions. */ }
}

function syncFavorites() {
  const count = state.favorites.size;
  $('#favorites-count').textContent = count;
  $('#favorites-count').hidden = count === 0;
  $('#favorites-nav').setAttribute('aria-label', `Mes favoris${count ? ` (${count})` : ''}`);
  $('#favorites-nav').setAttribute('aria-pressed', String(state.view === 'favorites'));
  $$('[data-favorite]').forEach(button => {
    const saved = state.favorites.has(button.dataset.favorite);
    button.classList.toggle('saved', saved);
    button.setAttribute('aria-pressed', String(saved));
    button.setAttribute('aria-label', saved ? 'Retirer des favoris' : 'Ajouter aux favoris');
    const label = $('.favorite-label', button);
    if (label) label.textContent = saved ? 'Enregistré' : 'Favori';
  });
}
function toggleFavorite(id) {
  const wasSaved = state.favorites.has(id);
  if (!wasSaved && state.favorites.size >= 200) { toast('Votre sélection est limitée à 200 favoris.', true); return; }
  if (wasSaved) state.favorites.delete(id); else state.favorites.add(id);
  saveStorage(STORAGE_FAVORITES, [...state.favorites]);
  syncFavorites();
  toast(wasSaved ? 'Annonce retirée de vos favoris.' : 'Une bonne adresse gardée de côté.');
  if (state.view === 'favorites') loadListings();
}

function updateDetailUrl(id = null) {
  const url = new URL(location.href);
  if (id) url.searchParams.set('annonce', id); else url.searchParams.delete('annonce');
  history.replaceState(null, '', url);
}
function detailHtml(item) {
  const saved = state.favorites.has(item.id);
  const id = escapeHtml(item.id);
  const image = item.images[0] ? `<img class="detail-main-photo" id="detail-main-photo" src="${escapeHtml(item.images[0])}" alt="${escapeHtml(item.title)}">` : noPhoto();
  const thumbs = item.images.length > 1 ? `<div class="detail-thumbs">${item.images.map((url, index) => `<button class="detail-thumb ${index === 0 ? 'active' : ''}" data-photo="${index}" aria-label="Voir la photo ${index + 1}" aria-pressed="${index === 0}"><img src="${escapeHtml(url)}" alt="" loading="lazy"></button>`).join('')}</div>` : '';
  const initials = item.contact_name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  const date = new Intl.DateTimeFormat('fr-FR', {day:'numeric', month:'long', year:'numeric'}).format(new Date(item.created_at));
  const specs = `<div>${icon('area')}<div><strong>${number(item.surface)} m²</strong><span>de surface</span></div></div>${item.rooms ? `<div>${icon('room')}<div><strong>${item.rooms}</strong><span>pièce${item.rooms > 1 ? 's' : ''}</span></div></div>` : ''}${item.bedrooms ? `<div>${icon('bed')}<div><strong>${item.bedrooms}</strong><span>chambre${item.bedrooms > 1 ? 's' : ''}</span></div></div>` : ''}`;
  const ownerActions = state.ownerKeys[item.id] ? `<div class="owner-actions"><button class="text-button" data-edit>${icon('edit')} Modifier</button><button class="text-button danger-button" data-delete-start>${icon('trash')} Supprimer</button></div><div class="delete-confirm" id="delete-confirm" hidden><p>Supprimer définitivement cette annonce ? Cette action est irréversible.</p><div><button class="text-button danger-button" data-delete-confirm>Oui, supprimer</button><button class="text-button" data-delete-cancel>Annuler</button></div></div>` : '';
  return `<article><div class="detail-photo-area">${image}<span class="transaction-badge ${item.transaction_type === 'location' ? 'rent' : ''}">${item.transaction_type === 'vente' ? 'À vendre' : 'À louer'}</span>${thumbs}</div><div class="detail-content"><div class="detail-heading"><div><p class="detail-property-type">${escapeHtml(types[item.property_type])}</p><h2>${escapeHtml(item.title)}</h2><p class="detail-location">${icon('pin')}${escapeHtml(item.district ? `${item.district}, ${item.city}` : item.city)}</p></div><div class="detail-price">${number(item.price)}<span>DT</span><small>${item.transaction_type === 'location' ? 'par mois · hors charges' : 'prix de vente'}</small></div></div><div class="detail-lower"><div><div class="detail-specs">${specs}</div><h3 class="detail-section-title">Un peu plus sur ce lieu</h3><p class="detail-description">${escapeHtml(item.description)}</p>${item.amenities.length ? `<h3 class="detail-section-title">Ce qui fait la différence</h3><div class="detail-amenities">${item.amenities.map(amenity => `<span>${icon('check')}${escapeHtml(amenity)}</span>`).join('')}</div>` : ''}<p class="detail-date">Publiée le ${escapeHtml(date)} · Réf. ${id}</p>${item.is_demo ? `<div class="demo-detail-note">${icon('info')}<span>Annonce fictive de démonstration. Les photos sont illustratives, aucun bien n’est réellement proposé.</span></div>` : ''}</div><aside><div class="contact-card"><p class="contact-title">LE BON CONTACT</p><div class="contact-person"><span class="contact-avatar">${escapeHtml(initials)}</span><div><strong>${escapeHtml(item.contact_name)}</strong><small>${item.is_demo ? 'Profil de démonstration' : 'Annonceur'}</small></div></div><button class="button button-dark" data-contact>${icon(item.is_demo ? 'info' : 'phone')}${item.is_demo ? 'À propos de cette démo' : 'Contacter l’annonceur'}</button><p class="contact-hint">${item.is_demo ? 'Annonce fictive · aucun contact réel.' : 'Un contact direct, pour une vraie rencontre.'}</p><div class="contact-reveal" id="contact-reveal" hidden></div></div><div class="detail-secondary-actions"><button class="button button-outline ${saved ? 'saved' : ''}" data-favorite="${id}" aria-pressed="${saved}" aria-label="${saved ? 'Retirer des favoris' : 'Ajouter aux favoris'}">${icon('heart')}<span class="favorite-label">${saved ? 'Enregistré' : 'Favori'}</span></button><button class="button button-outline" data-share>${icon('share')} Partager</button></div>${ownerActions}</aside></div></div></article>`;
}
async function openDetail(id) {
  const version = ++state.detailVersion;
  state.currentListing = null;
  $('#detail-body').innerHTML = '<div class="dialog-loading"><span class="spinner"></span>Une bonne adresse se dévoile…</div>';
  showDialog('detail-dialog');
  updateDetailUrl(id);
  try {
    const item = await request(`/api/listings/${encodeURIComponent(id)}`);
    if (version !== state.detailVersion || !$('#detail-dialog').open) return;
    state.currentListing = item;
    $('#detail-body').innerHTML = detailHtml(item);
  } catch (error) {
    if (version !== state.detailVersion || !$('#detail-dialog').open) return;
    $('#detail-body').innerHTML = `<div class="empty-state">${icon('info')}<h3>Cette adresse n’est plus disponible.</h3><p>${escapeHtml(error.message)}</p><button class="button button-dark" data-close="detail-dialog">Retour aux annonces</button></div>`;
  }
}
function revealContact() {
  const item = state.currentListing;
  if (!item) return;
  const box = $('#contact-reveal');
  if (item.is_demo) box.innerHTML = '<p class="contact-demo">Cette annonce est un exemple pour tester Dar. Publiez votre propre bien pour utiliser le contact direct.</p>';
  else {
    const phone = item.contact_phone ? `<a href="tel:${escapeHtml(item.contact_phone.replace(/[^+\d]/g, ''))}">${icon('phone')}${escapeHtml(item.contact_phone)}</a>` : '';
    const email = item.contact_email ? `<a href="mailto:${escapeHtml(encodeURIComponent(item.contact_email).replace(/%40/g, '@'))}">${icon('mail')}${escapeHtml(item.contact_email)}</a>` : '';
    box.innerHTML = phone + email;
  }
  box.hidden = !box.hidden;
  $('[data-contact]').setAttribute('aria-expanded', String(!box.hidden));
}
async function copyLink() {
  const text = new URL(`/?annonce=${encodeURIComponent(state.currentListing.id)}`, location.href).href;
  try {
    await navigator.clipboard.writeText(text);
    toast('Le lien de l’annonce a été copié.');
  } catch {
    const input = document.createElement('textarea');
    input.value = text;
    input.style.cssText = 'position:fixed;left:-9999px;top:0';
    $('#detail-dialog').append(input);
    input.select();
    const copied = document.execCommand('copy');
    input.remove();
    toast(copied ? 'Le lien de l’annonce a été copié.' : `Lien à copier : ${text}`, !copied);
  }
}
async function deleteListing(button) {
  const item = state.currentListing;
  if (!item || !state.ownerKeys[item.id]) return;
  button.disabled = true;
  button.textContent = 'Suppression…';
  try {
    await request(`/api/listings/${encodeURIComponent(item.id)}`, {method:'DELETE', headers:{'X-Edit-Token':state.ownerKeys[item.id]}});
    delete state.ownerKeys[item.id];
    saveStorage(STORAGE_KEYS, state.ownerKeys);
    state.favorites.delete(item.id);
    saveStorage(STORAGE_FAVORITES, [...state.favorites]);
    closeDialog('detail-dialog');
    syncUi();
    loadListings();
    loadStats();
    toast('Votre annonce a été supprimée.');
  } catch (error) { button.disabled = false; button.textContent = 'Oui, supprimer'; toast(error.message, true); }
}

function clearPhotoState() {
  state.photos.forEach(photo => { if (photo.preview?.startsWith('blob:')) URL.revokeObjectURL(photo.preview); });
  state.photos = [];
}
function openPublish(item = null) {
  if ($('#detail-dialog').open) closeDialog('detail-dialog');
  state.publishVersion++;
  clearPhotoState();
  state.submitting = false;
  state.editingId = item?.id || null;
  const form = $('#listing-form');
  form.reset();
  $('#form-error').hidden = true;
  $('#publish-title').innerHTML = item ? 'Votre bien, à jour<span>.</span>' : 'Parlons de votre bien<span>.</span>';
  $('#publish-subtitle').textContent = item ? 'Les bonnes informations font les bonnes rencontres.' : 'Quelques détails suffisent pour faire la bonne rencontre.';
  if (item) {
    for (const key of ['title','description','transaction_type','property_type','price','city','district','surface','rooms','bedrooms','contact_name','contact_email','contact_phone']) {
      form.elements.namedItem(key).value = item[key];
    }
    $$('[name="amenities"]', form).forEach(input => { input.checked = item.amenities.includes(input.value); });
    state.photos = item.images.map(url => ({id:crypto.randomUUID(), url, preview:url, uploading:false}));
  }
  updatePriceLabel();
  renderPhotos();
  updatePublishButton();
  showDialog('publish-dialog');
  setTimeout(() => form.elements.title.focus({preventScroll:true}), 80);
}
function updatePriceLabel() {
  const rent = $('#listing-form').elements.transaction_type.value === 'location';
  $('#price-label').textContent = rent ? 'Loyer mensuel (DT) *' : 'Prix de vente (DT) *';
}
function updatePublishButton() {
  const uploading = state.photos.some(photo => photo.uploading);
  const button = $('#publish-submit');
  button.disabled = state.submitting || uploading;
  button.innerHTML = state.submitting ? '<span class="spinner"></span> Un instant…' : uploading ? '<span class="spinner"></span> Envoi des photos…' : `${state.editingId ? 'Enregistrer les modifications' : 'Publier mon annonce'} ${icon('arrow-up')}`;
}
function renderPhotos() {
  $('#photo-previews').innerHTML = state.photos.map(photo => `<div class="photo-preview"><img src="${escapeHtml(photo.preview)}" alt="Photo de l’annonce">${photo.uploading ? '<div class="upload-loading"><span class="spinner"></span></div>' : ''}<button type="button" data-remove-photo="${escapeHtml(photo.id)}" aria-label="Retirer cette photo">${icon('close')}</button></div>`).join('');
  updatePublishButton();
}
async function addPhotos(files) {
  const version = state.publishVersion;
  const available = 6 - state.photos.length;
  const selection = [...files].slice(0, available);
  if (files.length > available) toast('Vous pouvez ajouter jusqu’à 6 photos par annonce.', true);
  await Promise.all(selection.map(async file => {
    if (file.size > 8 * 1024 * 1024) { toast('Une photo dépasse 8 Mo. Choisissez une version plus légère.', true); return; }
    if (!['image/jpeg','image/png','image/webp'].includes(file.type)) { toast('Choisissez une photo JPEG, PNG ou WebP.', true); return; }
    const photo = {id:crypto.randomUUID(), preview:URL.createObjectURL(file), url:null, uploading:true};
    state.photos.push(photo);
    renderPhotos();
    const data = new FormData();
    data.append('file', file);
    try {
      const response = await request('/api/uploads', {method:'POST', body:data});
      if (version !== state.publishVersion || !state.photos.includes(photo)) return;
      URL.revokeObjectURL(photo.preview);
      photo.preview = response.url;
      photo.url = response.url;
      photo.uploading = false;
    } catch (error) {
      if (version !== state.publishVersion || !state.photos.includes(photo)) return;
      URL.revokeObjectURL(photo.preview);
      state.photos = state.photos.filter(item => item !== photo);
      toast(error.message, true);
    } finally {
      if (version === state.publishVersion) renderPhotos();
    }
  }));
}
async function publishListing(event) {
  event.preventDefault();
  if (state.submitting || state.photos.some(photo => photo.uploading)) return;
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const values = new FormData(form);
  const data = {};
  for (const field of ['title','description','transaction_type','property_type','city','district','contact_name','contact_email','contact_phone']) data[field] = String(values.get(field) || '').trim();
  for (const field of ['price','surface','rooms','bedrooms']) data[field] = Number(values.get(field));
  data.amenities = values.getAll('amenities');
  data.images = state.photos.filter(photo => photo.url).map(photo => photo.url);
  let validation = '';
  if (data.title.length < 5) validation = 'Donnez un titre d’au moins 5 caractères à votre annonce.';
  else if (data.description.length < 20) validation = 'Racontez votre bien en au moins 20 caractères.';
  else if (!data.contact_email && !data.contact_phone) validation = 'Ajoutez au moins un e-mail ou un téléphone pour être contacté.';
  else if (data.bedrooms > data.rooms) validation = 'Le nombre de chambres ne peut pas dépasser le nombre de pièces.';
  if (validation) { $('#form-error').textContent = validation; $('#form-error').hidden = false; $('#form-error').scrollIntoView({behavior:'smooth', block:'center'}); return; }
  state.submitting = true;
  updatePublishButton();
  $('#form-error').hidden = true;
  const editId = state.editingId;
  try {
    const response = await request(editId ? `/api/listings/${encodeURIComponent(editId)}` : '/api/listings', {
      method:editId ? 'PUT' : 'POST',
      headers:{'Content-Type':'application/json', ...(editId ? {'X-Edit-Token':state.ownerKeys[editId]} : {})},
      body:JSON.stringify(data)
    });
    state.submitting = false;
    closeDialog('publish-dialog');
    loadStats();
    if (editId) {
      toast('Votre annonce est à jour.');
      loadListings();
      openDetail(editId);
    } else {
      state.ownerKeys[response.listing.id] = response.edit_token;
      const saved = saveStorage(STORAGE_KEYS, state.ownerKeys);
      state.lastCreated = response;
      $('#created-key').textContent = response.edit_token;
      $('.secret-details').open = !saved;
      if (!saved) toast('Le stockage du navigateur est indisponible. Téléchargez votre clé secrète.', true);
      setView('mine', '', false);
      showDialog('success-dialog');
    }
  } catch (error) {
    $('#form-error').textContent = error.message;
    $('#form-error').hidden = false;
    $('#form-error').scrollIntoView({behavior:'smooth', block:'center'});
  } finally {
    state.submitting = false;
    updatePublishButton();
  }
}
function downloadKey() {
  if (!state.lastCreated) return;
  const {listing, edit_token} = state.lastCreated;
  const blob = new Blob([JSON.stringify({application:'Dar.', listing_id:listing.id, edit_token, usage:'Clé privée. À fournir dans X-Edit-Token pour PUT ou DELETE /api/listings/{listing_id}. Ne pas partager.'}, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `dar-cle-privee-${listing.id}.json`;
  $('#success-dialog').append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
  toast('Votre clé privée a été téléchargée. Gardez-la en lieu sûr.');
}

// Événements : une seule délégation pour les contenus créés dynamiquement.
document.addEventListener('click', event => {
  const button = event.target.closest('button, a');
  if (!button) return;
  if (button.hasAttribute('data-close')) { event.preventDefault(); closeDialog(button.dataset.close); }
  else if (button.hasAttribute('data-favorite')) { event.preventDefault(); toggleFavorite(button.dataset.favorite); }
  else if (button.hasAttribute('data-open')) { event.preventDefault(); openDetail(button.dataset.open); }
  else if (button.hasAttribute('data-publish')) { event.preventDefault(); openPublish(); }
  else if (button.hasAttribute('data-nav')) {
    const nav = button.dataset.nav;
    if (nav === 'mine') setView('mine'); else setView('all', nav === 'all' ? '' : nav, nav !== 'all');
    if (nav === 'all') window.scrollTo({top:0, behavior:'smooth'});
  }
  else if (button.hasAttribute('data-mode')) { state.view = 'all'; state.transaction = button.dataset.mode; syncUi(); loadListings(); }
  else if (button.hasAttribute('data-type')) { state.propertyType = button.dataset.type; syncUi(); loadListings(); }
  else if (button.hasAttribute('data-reset')) { resetFilters(); syncUi(); loadListings(); }
  else if (button.hasAttribute('data-explore')) setView('all');
  else if (button.hasAttribute('data-retry')) loadListings();
  else if (button.hasAttribute('data-photo') && state.currentListing) {
    const index = Number(button.dataset.photo);
    $('#detail-main-photo').src = state.currentListing.images[index];
    $$('[data-photo]').forEach(thumb => { const active = thumb === button; thumb.classList.toggle('active', active); thumb.setAttribute('aria-pressed', String(active)); });
  }
  else if (button.hasAttribute('data-contact')) revealContact();
  else if (button.hasAttribute('data-share') && state.currentListing) copyLink();
  else if (button.hasAttribute('data-edit') && state.currentListing) openPublish(state.currentListing);
  else if (button.hasAttribute('data-delete-start')) $('#delete-confirm').hidden = false;
  else if (button.hasAttribute('data-delete-cancel')) $('#delete-confirm').hidden = true;
  else if (button.hasAttribute('data-delete-confirm')) deleteListing(button);
  else if (button.hasAttribute('data-remove-photo')) {
    const photo = state.photos.find(item => item.id === button.dataset.removePhoto);
    if (photo?.preview?.startsWith('blob:')) URL.revokeObjectURL(photo.preview);
    state.photos = state.photos.filter(item => item !== photo);
    renderPhotos();
  }
});
$('#brand').addEventListener('click', event => { event.preventDefault(); setView('all', '', false); window.scrollTo({top:0, behavior:'smooth'}); });
$('#favorites-nav').addEventListener('click', () => setView(state.view === 'favorites' ? 'all' : 'favorites'));
$('#search-form').addEventListener('submit', event => {
  event.preventDefault();
  state.q = $('#search-q').value.trim();
  state.propertyType = $('#search-type').value;
  state.maxPrice = $('#search-budget').value;
  syncUi();
  loadListings({scroll:true});
});
$('#search-type').addEventListener('change', event => { state.q = $('#search-q').value.trim(); state.maxPrice = $('#search-budget').value; state.propertyType = event.target.value; syncUi(); loadListings(); });
$('#sort-select').addEventListener('change', event => { state.sort = event.target.value; loadListings(); });
$('#filter-toggle').addEventListener('click', () => {
  const expanded = $('#filter-toggle').getAttribute('aria-expanded') === 'true';
  $('#filter-toggle').setAttribute('aria-expanded', String(!expanded));
  $('#advanced-filters').hidden = expanded;
});
$('#apply-filters').addEventListener('click', () => {
  if (!$('#filter-surface').reportValidity()) return;
  state.minSurface = $('#filter-surface').value;
  state.minRooms = $('#filter-rooms').value;
  syncUi();
  loadListings();
});
for (const id of ['clear-filters', 'reset-search']) document.getElementById(id).addEventListener('click', () => { resetFilters(); syncUi(); loadListings(); });
$('#load-more').addEventListener('click', () => { $('#load-more').disabled = true; loadListings({append:true}); });
$('#listing-form').addEventListener('submit', publishListing);
$$('[name="transaction_type"]').forEach(input => input.addEventListener('change', updatePriceLabel));
$('#photo-input').addEventListener('change', event => { addPhotos(event.target.files); event.target.value = ''; });
$('#upload-zone').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#photo-input').click(); } });
for (const type of ['dragenter', 'dragover']) $('#upload-zone').addEventListener(type, event => { event.preventDefault(); $('#upload-zone').classList.add('dragover'); });
for (const type of ['dragleave', 'drop']) $('#upload-zone').addEventListener(type, event => { event.preventDefault(); $('#upload-zone').classList.remove('dragover'); });
$('#upload-zone').addEventListener('drop', event => addPhotos(event.dataTransfer.files));
$('#see-created').addEventListener('click', () => { closeDialog('success-dialog'); if (state.lastCreated) openDetail(state.lastCreated.listing.id); });
$('#download-key').addEventListener('click', downloadKey);
$$('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog(dialog.id);
  });
  dialog.addEventListener('cancel', event => {
    if (dialog.id === 'publish-dialog' && state.submitting) { event.preventDefault(); toast('La publication est en cours, encore un instant.'); }
  });
  dialog.addEventListener('close', () => {
    if (dialog.id === 'detail-dialog') { state.detailVersion++; state.currentListing = null; updateDetailUrl(); }
    if (dialog.id === 'publish-dialog') { state.publishVersion++; clearPhotoState(); }
    updateScrollLock();
  });
});
document.addEventListener('error', event => {
  if (event.target.tagName === 'IMG' && !event.target.src.endsWith('/static/images/fallback.svg')) event.target.src = '/static/images/fallback.svg';
}, true);
$('#amenities-options').innerHTML = amenities.map(amenity => `<label><input type="checkbox" name="amenities" value="${escapeHtml(amenity)}"><span>${escapeHtml(amenity)}</span></label>`).join('');
$('#year').textContent = new Date().getFullYear();
const initialListing = new URLSearchParams(location.search).get('annonce');
syncUi();
loadListings();
loadStats();
if (initialListing) openDetail(initialListing);
