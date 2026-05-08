document.getElementById('run-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);

  const res = await fetch('/run', { method: 'POST', body: data });
  const j = await res.json();
  if (res.ok) {
    const jobId = j.job_id;
    const container = document.getElementById('jobs');
    const el = document.createElement('div');
    el.id = `job-${jobId}`;
    el.innerHTML = `<h3>Job ${jobId}</h3><div class="status">Queued</div><div class="result"></div>`;
    container.prepend(el);
    pollStatus(jobId);
  } else {
    alert(JSON.stringify(j));
  }
});

async function pollStatus(jobId) {
  const el = document.getElementById(`job-${jobId}`);
  const statusEl = el.querySelector('.status');
  const resultEl = el.querySelector('.result');

  let done = false;
  while (!done) {
    const res = await fetch(`/status/${jobId}`);
    const j = await res.json();
    statusEl.textContent = j.status || 'unknown';
    if (j.status === 'finished') {
      done = true;
      const r = j.result;
      resultEl.innerHTML = `
        <h4>Pipeline: ${r.pipeline}</h4>
        <div class="players">
          <div class="player">
            <h5>Player A: ${r.player_a.pins} pins</h5>
            <a href="/outputs/${jobId}_A_${r.pipeline}.mp4" target="_blank">Download annotated A</a>
          </div>
          <div class="player">
            <h5>Player B: ${r.player_b.pins} pins</h5>
            <a href="/outputs/${jobId}_B_${r.pipeline}.mp4" target="_blank">Download annotated B</a>
          </div>
        </div>
      `;

      // show winner confetti placeholder (client can integrate canvas-confetti)
      const winner = r.player_a.pins > r.player_b.pins ? 'A' : (r.player_b.pins > r.player_a.pins ? 'B' : 'Tie');
      const winEl = document.createElement('div');
      winEl.className = 'winner';
      winEl.textContent = `Winner: ${winner}`;
      resultEl.prepend(winEl);
    } else if (j.status === 'error') {
      done = true;
      resultEl.textContent = `Error: ${j.error}`;
    } else {
      await new Promise(r => setTimeout(r, 1500));
    }
  }
}

