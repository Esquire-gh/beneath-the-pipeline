/* Beneath the Pipeline — navigation, progress, copy buttons. Nothing else.
 *
 * Runs from file://, so there is no fetch() anywhere in here. Progress lives
 * in localStorage, which file:// pages are allowed to use.
 */
(function () {
  'use strict';

  var KEY = 'btp.completed.v1';

  function readDone() {
    try {
      var raw = window.localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function writeDone(list) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(list));
    } catch (e) { /* private browsing; progress just won't persist */ }
  }

  /* ---- copy buttons on every code block ------------------------------ */

  function addCopyButtons() {
    var blocks = document.querySelectorAll('.code');
    Array.prototype.forEach.call(blocks, function (block) {
      if (block.querySelector('.copy')) return;
      var pre = block.querySelector('pre');
      if (!pre) return;

      var btn = document.createElement('button');
      btn.className = 'copy';
      btn.type = 'button';
      btn.textContent = 'copy';
      btn.setAttribute('aria-label', 'Copy code to clipboard');

      btn.addEventListener('click', function () {
        var text = pre.innerText;
        var done = function () {
          btn.textContent = 'copied';
          btn.classList.add('copied');
          window.setTimeout(function () {
            btn.textContent = 'copy';
            btn.classList.remove('copied');
          }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {
            legacyCopy(text, done);
          });
        } else {
          legacyCopy(text, done);
        }
      });

      block.appendChild(btn);
    });
  }

  /* file:// in some browsers refuses the async clipboard API. */
  function legacyCopy(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { /* nothing to do */ }
    document.body.removeChild(ta);
  }

  /* ---- "I finished this module" -------------------------------------- */

  function wireDoneToggle() {
    var btn = document.querySelector('.done-toggle');
    if (!btn) return;
    var slug = btn.getAttribute('data-module');
    if (!slug) return;

    var render = function () {
      var on = readDone().indexOf(slug) !== -1;
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.querySelector('.label').textContent = on
        ? 'module complete'
        : 'mark this module complete';
    };

    btn.addEventListener('click', function () {
      var list = readDone();
      var i = list.indexOf(slug);
      if (i === -1) { list.push(slug); } else { list.splice(i, 1); }
      writeDone(list);
      render();
    });

    render();
  }

  /* ---- table of contents shows what you have finished ---------------- */

  function markTableOfContents() {
    var done = readDone();
    var links = document.querySelectorAll('.toc a[data-module]');
    var n = 0;
    Array.prototype.forEach.call(links, function (a) {
      if (done.indexOf(a.getAttribute('data-module')) !== -1) {
        a.classList.add('is-done');
        n += 1;
      }
    });
    var counter = document.querySelector('[data-progress-count]');
    if (counter) {
      counter.textContent = n + ' / ' + links.length + ' complete';
    }
  }

  /* ---- the sidebar ticks the modules you have finished ---------------- */

  function markSidebar() {
    var done = readDone();
    var links = document.querySelectorAll('.sitenav a[data-module]');
    Array.prototype.forEach.call(links, function (a) {
      if (done.indexOf(a.getAttribute('data-module')) !== -1) {
        a.classList.add('done');
      }
    });
  }

  /* ---- on a narrow screen the sidebar is behind the menu button ------- */

  function wireNavToggle() {
    var btn = document.querySelector('.nav-toggle');
    var rail = document.getElementById('sitenav-panel');
    if (!btn || !rail) { return; }
    btn.addEventListener('click', function () {
      var open = rail.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.textContent = open ? 'close' : 'menu';
    });
  }

  /* ---- keep the current module in view inside a long sidebar ---------- */

  function scrollNavToCurrent() {
    var rail = document.getElementById('sitenav-panel');
    var current = rail && rail.querySelector('.current');
    /* A rail with no height has not been laid out yet — a background tab, for
       instance. Measuring it now would just pin the scroll to the top. */
    if (!rail || !current || !rail.clientHeight) { return; }
    var top = current.offsetTop - rail.clientHeight / 2;
    rail.scrollTop = top > 0 ? top : 0;
  }

  function scrollNavToCurrentSoon() {
    window.requestAnimationFrame(scrollNavToCurrent);
  }

  function init() {
    addCopyButtons();
    wireDoneToggle();
    markTableOfContents();
    markSidebar();
    wireNavToggle();
    scrollNavToCurrent();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* The rail can only be measured once it is laid out, and a page that opens in
     a background tab is not laid out until it is looked at. */
  window.addEventListener('load', scrollNavToCurrentSoon);
  document.addEventListener('visibilitychange', scrollNavToCurrentSoon);
  window.setTimeout(scrollNavToCurrent, 200);
}());
