document.getElementById('run-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById('submit-btn');
  const data = new FormData(form);

  btn.disabled = true;
  btn.textContent = "Uploading...";

  try {
    const res = await fetch('/run', { method: 'POST', body: data });
    const j = await res.json();
    if (res.ok) {
      const jobId = j.job_id;
      const container = document.getElementById('jobs');

      const el = document.createElement('div');
      el.id = `job-${jobId}`;
      el.className = 'job-card';
      el.innerHTML = `
        <h3>Match Analysis ID: ${jobId}</h3>
        <div class="status-row">
            <div class="loader" id="loader-${jobId}"></div>
            <div class="status" id="status-${jobId}">Initializing AI Engine...</div>
        </div>
        <div class="result"></div>
      `;
      container.prepend(el);
      pollStatus(jobId);
      form.reset();
    } else {
      alert(j.error || "Upload failed");
    }
  } catch (err) {
    alert("Server error: " + err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run AI Analysis";
  }
});

async function pollStatus(jobId) {
  const el = document.getElementById(`job-${jobId}`);
  const statusEl = document.getElementById(`status-${jobId}`);
  const loaderEl = document.getElementById(`loader-${jobId}`);
  const resultEl = el.querySelector('.result');

  let done = false;
  while (!done) {
    const res = await fetch(`/status/${jobId}`);
    const j = await res.json();

    if (j.status === 'running') {
        statusEl.textContent = "AI is currently tracking pins... This may take a few minutes.";
    } else {
        statusEl.textContent = j.status;
    }

    if (j.status === 'finished') {
      done = true;
      el.classList.add('finished');
      loaderEl.style.display = 'none';
      statusEl.textContent = "Analysis Complete!";

      const r = j.result;

      // Determine winner
      let winnerText = "It's a TIE!";
      if (r.player_a.pins > r.player_b.pins) winnerText = "Player A Wins! 🏆";
      if (r.player_b.pins > r.player_a.pins) winnerText = "Player B Wins! 🏆";

      resultEl.innerHTML = `
        <div class="winner-banner">${winnerText}</div>
        <div class="players">
          <div class="player">
            <h5>Player A: ${r.player_a.pins} Pins</h5>
            <p>Time: ${r.player_a.elapsed_s.toFixed(1)}s</p>
            <a href="/outputs/${jobId}_A_${r.pipeline}.mp4" target="_blank">View Video A</a>
          </div>
          <div class="player">
            <h5>Player B: ${r.player_b.pins} Pins</h5>
            <p>Time: ${r.player_b.elapsed_s.toFixed(1)}s</p>
            <a href="/outputs/${jobId}_B_${r.pipeline}.mp4" target="_blank">View Video B</a>
          </div>
        </div>
      `;

      // Trigger Confetti if there was a clear winner
      if (r.player_a.pins !== r.player_b.pins) {
        confetti({
            particleCount: 150,
            spread: 80,
            origin: { y: 0.6 }
        });
      }

    } else if (j.status === 'error') {
      done = true;
      el.classList.add('error');
      loaderEl.style.display = 'none';
      statusEl.textContent = "Failed";
      resultEl.innerHTML = `<p style="color:red;">Error: ${j.error}</p>`;
    } else {
      await new Promise(r => setTimeout(r, 1500));
    }
  }
}