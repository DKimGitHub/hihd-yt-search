// Animated night sky behind the page: a static starfield with star clusters,
// a few twinkling stars and an occasional shooting star.
// Honors prefers-reduced-motion (draws once, no animation).
(() => {
  const canvas = document.getElementById("sky");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TINTS = ["255,255,255", "255,244,224", "214,226,255", "196,214,255", "255,224,196"];

  let w = 0, h = 0, dpr = 1, field = null, twinklers = [], shooting = null, nextShot = 0;

  // Deterministic PRNG so the sky doesn't reshuffle on every resize.
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  const gauss = () => { let u = 0, v = 0; while (!u) u = rand(); while (!v) v = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };

  function star(c, x, y, r, a, tint) {
    c.fillStyle = `rgba(${tint},${a})`;
    c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
    if (r > 1.0) { // soft halo on the brightest stars
      const g = c.createRadialGradient(x, y, 0, x, y, r * 5);
      g.addColorStop(0, `rgba(${tint},${a * 0.35})`); g.addColorStop(1, `rgba(${tint},0)`);
      c.fillStyle = g; c.beginPath(); c.arc(x, y, r * 5, 0, Math.PI * 2); c.fill();
    }
  }

  function build() {
    seed = 7;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    // Size for the tallest viewport (address bar hidden) so no gap appears on scroll.
    w = innerWidth; h = Math.max(innerHeight, screen.height || 0);
    canvas.width = w * dpr; canvas.height = h * dpr;
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    field = document.createElement("canvas");
    field.width = canvas.width; field.height = canvas.height;
    const c = field.getContext("2d");
    c.scale(dpr, dpr);

    // Background dust.
    const n = Math.round((w * h) / 1100);
    for (let i = 0; i < n; i++) {
      const r = rand() < 0.9 ? rand() * 0.8 + 0.45 : rand() * 1.2 + 1.1;
      star(c, rand() * w, rand() * h, r, rand() * 0.6 + 0.35, TINTS[(rand() * TINTS.length) | 0]);
    }
    // Star clusters: dense gaussian knots with a faint glow.
    const clusters = Math.max(2, Math.round((w * h) / 380000));
    for (let k = 0; k < clusters; k++) {
      const cx = rand() * w, cy = rand() * h, spread = 30 + rand() * 70;
      const glow = c.createRadialGradient(cx, cy, 0, cx, cy, spread * 2.2);
      glow.addColorStop(0, "rgba(190,200,255,0.16)"); glow.addColorStop(1, "rgba(190,200,255,0)");
      c.fillStyle = glow; c.beginPath(); c.arc(cx, cy, spread * 2.2, 0, Math.PI * 2); c.fill();
      const m = 90 + rand() * 140;
      for (let i = 0; i < m; i++) {
        star(c, cx + gauss() * spread, cy + gauss() * spread * 0.8, rand() * 0.9 + 0.4,
             rand() * 0.5 + 0.5, TINTS[(rand() * TINTS.length) | 0]);
      }
    }
    // Stars that twinkle (drawn live).
    twinklers = Array.from({ length: Math.round((w * h) / 22000) + 12 }, () => ({
      x: rand() * w, y: rand() * h, r: rand() * 1.2 + 1.0,
      phase: rand() * Math.PI * 2, speed: 0.6 + rand() * 1.6, tint: TINTS[(rand() * TINTS.length) | 0],
    }));
    draw(0);
  }

  function draw(t) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(field, 0, 0);
    ctx.scale(dpr, dpr);
    for (const s of twinklers) {
      const a = still ? 0.8 : 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(s.phase + (t / 1000) * s.speed));
      star(ctx, s.x, s.y, s.r, a, s.tint);
    }
    if (shooting) {
      const p = (t - shooting.t0) / shooting.dur;
      if (p >= 1) shooting = null;
      else {
        const x = shooting.x + shooting.dx * p, y = shooting.y + shooting.dy * p;
        const g = ctx.createLinearGradient(x, y, x - shooting.dx * 0.18, y - shooting.dy * 0.18);
        const a = Math.sin(p * Math.PI);
        g.addColorStop(0, `rgba(255,255,255,${a})`); g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.strokeStyle = g; ctx.lineWidth = 1.4; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - shooting.dx * 0.18, y - shooting.dy * 0.18); ctx.stroke();
      }
    }
  }

  let last = 0;
  function loop(t) {
    if (t - last > 50) { // ~20 fps is plenty for twinkling
      if (!shooting && t > nextShot) {
        shooting = { x: Math.random() * w * 0.8 + w * 0.1, y: Math.random() * h * 0.4,
                     dx: (Math.random() < 0.5 ? -1 : 1) * (180 + Math.random() * 160), dy: 90 + Math.random() * 90,
                     t0: t, dur: 900 };
        nextShot = t + 9000 + Math.random() * 14000;
      }
      draw(t); last = t;
    }
    requestAnimationFrame(loop);
  }

  let timer;
  // Phones resize the viewport when the address bar shows/hides while scrolling;
  // only rebuild for real size changes so the sky doesn't flicker.
  addEventListener("resize", () => {
    if (innerWidth === w && Math.abs(innerHeight - h) < 160) return;
    clearTimeout(timer); timer = setTimeout(build, 150);
  });
  build();
  if (!still) { nextShot = performance.now() + 4000; requestAnimationFrame(loop); }
})();
