<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Daily Casting Report</title>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="https://lebron1212.github.io/casting-tracker/styles.css" />
</head>
<body>
  <div id="casting-report"></div>
  <script>
function extractBlurbs(block) {
  const match = block.match(/BLURBS:\n([\s\S]*?)\n(?:Posted Date:|FULL ARTICLE TEXT:)/i);
  const blurbs = {};
  if (match) {
    match[1].split(/\n+/).forEach(line => {
      const [name, desc] = line.split(':').map(p => p.trim());
      if (name && desc) blurbs[name] = desc;
    });
  }
  return blurbs;
}
function actorSpan(str, blurbs) {
  if (!str || str.trim() === '' || str.toLowerCase().includes('none')) return 'UNKNOWN ACTOR';
  return str.replace(/B-TIER ACTORS:|A-TIER ACTORS:/gi, '')
    .split(/,\s*/).filter(n => n && n !== '[NONE]')
    .map(name => {
      const blurb = blurbs?.[name] || '';
      return `<span class='actor'>${name}${blurb ? `<span class='tooltip' title="${blurb}">${blurb}</span>` : ''}</span>`;
    }).join(', ') || 'UNKNOWN ACTOR';
}
function extractTag(block) {
  const match = block.match(/TAG:\s*(.+)/i);
  return match ? match[1].trim().toUpperCase() : 'UNKNOWN';
}
function extractProjectTitle(block) {
  const titleMatch = block.match(/ARTICLE TITLE:\s*(.+?)\n/i);
  if (!titleMatch) return 'UNTITLED PROJECT';
  const title = titleMatch[1];
  const quoted = title.match(/['"“”‘’](.+?)['"“”‘’]/);
  if (quoted) return quoted[1].toUpperCase();
  const strong = title.match(/([A-Z][A-Z0-9 :&'\-]{4,})/g);
  if (strong) {
    const blacklist = ['AND','THE','WITH','JOINS','CAST','OF','IN','TO','ON','BY','FROM','FOR','NEW','SERIES','MOVIE','PROJECT'];
    const clean = strong.filter(x => !blacklist.includes(x.trim()) && !x.match(/^([A-Z]{2,4})$/));
    if (clean.length > 0) return clean.sort((a, b) => b.length - a.length)[0].trim();
  }
  return 'UNTITLED PROJECT';
}
function getPostedDate(block) {
  const match = block.match(/POSTED DATE:\s*(\d{4}-\d{2}-\d{2})/i);
  return match ? match[1] : null;
}
function scrambleText(el, html, cb) {
  const div = document.createElement('div');
  div.innerHTML = html;
  div.querySelectorAll('.tooltip').forEach(t => t.remove());
  const ts = div.querySelector('.timestamp');
  let tsHTML = '';
  if (ts) { tsHTML = ts.outerHTML; ts.remove(); }
  const txt = div.textContent,
        glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*',
        out = Array(txt.length).fill(' '),
        span = document.createElement('span');
  span.className = 'scrambler';
  el.innerHTML = '';
  el.appendChild(span);
  function flip(i, c = 0) {
    if (c >= 5 || txt[i] === ' ') out[i] = txt[i];
    else {
      out[i] = glyphs[Math.floor(Math.random() * glyphs.length)];
      setTimeout(() => flip(i, c + 1), 20);
    }
    span.innerHTML = out.join('') + tsHTML;
  }
  function animate(i = 0) {
    if (i >= txt.length + 2) {
      el.innerHTML = html;
      el.querySelector('.timestamp')?.classList.add('visible');
      cb && cb();
      return;
    }
    if (i - 2 >= 0) flip(i - 2);
    setTimeout(() => animate(i + 1), 25);
  }
  animate();
}
async function renderReport() {
  const projectActorMap = new Map();
  localStorage.clear();
  const container = document.getElementById("casting-report"),
        res = await fetch("https://lebron1212.github.io/casting-tracker/reports/latest_casting_report.txt"),
        text = await res.text(),
        blocks = text.trim().split(/ARTICLE TITLE:/i).slice(1),
        now = new Date();

  const dateMap = new Map();
  for (const r of blocks) {
    const b = "ARTICLE TITLE:" + r.trim();
    const d = getPostedDate(b);
    if (!d) continue;
    if (!dateMap.has(d)) dateMap.set(d, []);
    dateMap.get(d).push(b);
  }

  const sortedDates = Array.from(dateMap.keys()).sort((a, b) => new Date(b) - new Date(a));
  const resultsByDate = [];

  for (const dateStr of sortedDates) {
    const blocks = dateMap.get(dateStr);
    const d = new Date(`${dateStr}T12:00:00`);
    const month = d.toLocaleDateString(undefined, { month: 'short' }).toUpperCase();
    const day = d.getDate();
    const dateHeader = `${month} ${day}`;

    const dayContainer = document.createElement("div");
    dayContainer.className = "day-group";
    dayContainer.dataset.date = dateStr;

    const header = document.createElement("h2");
    header.className = "day-header";
    header.textContent = dateHeader;
    dayContainer.appendChild(header);

    const formatted = blocks.map(b => {
      const a = b.match(/A-TIER ACTORS:\s*(.*)/i),
            bTier = b.match(/B-TIER ACTORS:\s*(.*)/i),
            pt = extractProjectTitle(b),
            tag = extractTag(b),
            posted = getPostedDate(b),
            blurbs = extractBlurbs(b);

      const aActors = a?.[1]?.replace(/[\[\]]/g, '').trim(),
            bActors = bTier?.[1]?.replace(/[\[\]]/g, '').trim();
      const hasA = !!aActors;
      const raw = hasA ? aActors : bActors || '';
      const shownActors = projectActorMap.get(pt) || new Set();
      const unique = raw.split(',').map(s => s.trim()).filter(n => n && !shownActors.has(n));
      if (!unique.length) return null;
      unique.forEach(n => shownActors.add(n));
      projectActorMap.set(pt, shownActors);
      const actorLine = actorSpan(unique.join(', '), blurbs);
      if (!actorLine || actorLine.includes('UNKNOWN')) return null;
      const postDate = new Date(`${posted}T12:00:00`);
      const h = Math.floor((now - postDate) / 36e5);
      const tagTime = h < 1 ? 'just now' : h < 24 ? `updated ${h} hours ago` : `updated ${Math.floor(h / 24)}D${h % 24}H ago`;
      return {
        rawText: `<span class='bold'>ATTACHED:</span> ${actorLine}. <em>${pt}</em>. (${tag})<span class='timestamp'>${tagTime}</span>`,
        hasATier: hasA
      };
    });

    const lines = formatted.filter(Boolean).map(r => {
      const div = document.createElement("div");
      div.className = "line cypher" + (r.hasATier ? " a-tier" : "");
      div.dataset.raw = r.rawText;
      return div;
    });

    lines.forEach(line => dayContainer.appendChild(line));
    resultsByDate.push({ dateStr, element: dayContainer, lines });
  }

  const showLimit = 2;
  let shown = 0;
  const allQueued = [];
  function showNextDay() {
    if (shown >= resultsByDate.length) return;
    const day = resultsByDate[shown++];
    container.appendChild(day.element);
    allQueued.push(...day.lines.map(el => ({ el, raw: el.dataset.raw })));
  }

  showNextDay();
  showNextDay();

  const loadBtn = document.createElement("button");
  loadBtn.textContent = "Load More";
  loadBtn.className = "load-more-btn";
  loadBtn.onclick = () => {
    let count = 0;
    while (shown < resultsByDate.length && count < 2) {
      showNextDay();
      count++;
    }
    if (shown >= resultsByDate.length) loadBtn.style.display = "none";
  };
  container.appendChild(loadBtn);

  let currentIndex = 0;
  function animateNext() {
    if (currentIndex >= allQueued.length) return;
    const { el, raw } = allQueued[currentIndex];
    scrambleText(el, raw, () => {
      currentIndex++;
      animateNext();
    });
  }
  animateNext();
}

document.addEventListener('mouseover', e => {
  const el = e.target.closest('.actor');
  if (!el) return;
  const tip = el.querySelector('.tooltip');
  if (!tip) return;
  tip.classList.remove('flip-up', 'flip-down');
  const r = tip.getBoundingClientRect();
  const spaceAbove = el.getBoundingClientRect().top;
  const spaceBelow = window.innerHeight - el.getBoundingClientRect().bottom;
  tip.classList.add(spaceBelow < r.height && spaceAbove > r.height ? 'flip-up' : 'flip-down');
});

renderReport();
  </script>
</body>
</html>
