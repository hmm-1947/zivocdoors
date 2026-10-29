(function () {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }
  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  var buttons = [];
  var deferred = null;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  function show(on) {
    buttons.forEach(function (b) { b.hidden = !on; });
  }
  function init() {
    buttons = Array.prototype.slice.call(document.querySelectorAll('[data-pwa-install]'));
    if (standalone) { show(false); return; }
    if (ios) { show(true); }
    buttons.forEach(function (b) {
      b.addEventListener('click', function () {
        if (deferred) {
          deferred.prompt();
          deferred.userChoice.then(function () { deferred = null; show(false); });
        } else if (ios) {
          alert('To install Zivoc: tap the Share button, then "Add to Home Screen".');
        }
      });
    });
  }
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    show(true);
  });
  window.addEventListener('appinstalled', function () {
    deferred = null;
    show(false);
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
