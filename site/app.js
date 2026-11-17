// Exercise gallery: cards switch the screenshot with a small transition.
// Without JS every screenshot stays visible (no hidden content).
(function () {
  var gallery = document.querySelector('[data-gallery]');
  if (!gallery) return;

  var cards = Array.prototype.slice.call(document.querySelectorAll('[data-exercise-tabs] [data-shot]'));
  var shots = Array.prototype.slice.call(gallery.querySelectorAll('.shot'));

  gallery.classList.add('is-enhanced');

  function show(key) {
    cards.forEach(function (card) {
      var on = card.getAttribute('data-shot') === key;
      card.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    shots.forEach(function (shot) {
      var on = shot.getAttribute('data-shot') === key;
      shot.classList.toggle('is-active', on);
      shot.setAttribute('aria-hidden', on ? 'false' : 'true');
    });
  }

  cards.forEach(function (card) {
    card.addEventListener('click', function () {
      show(card.getAttribute('data-shot'));
    });
  });

  show(cards.length ? cards[0].getAttribute('data-shot') : 'ex1');
})();
