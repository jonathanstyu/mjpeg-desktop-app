// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.
const PythonShell = require('python-shell').PythonShell;

const STORAGE_KEY = 'mjpeg.savedUrls.v1';
const MAX_SAVED_URLS = 20;

const statusBox = document.getElementById('alertbox');
const urlInput = document.getElementById('urlInput');
const imageCanvas = document.getElementById('imageCanvas');
const tableBody = document.getElementById('tableBody');

function setStatus(message, type = 'info') {
  statusBox.textContent = message;
  statusBox.classList.remove('success', 'error');

  if (type === 'success') {
    statusBox.classList.add('success');
  } else if (type === 'error') {
    statusBox.classList.add('error');
  }
}

function getVideoUrl() {
  const url = urlInput.value.trim();

  if (!url) {
    setStatus('Please enter a stream URL first.', 'error');
    return null;
  }

  return url;
}

function loadSavedUrls() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter((item) => item && typeof item.url === 'string')
      .map((item) => ({
        url: item.url.trim(),
        lastUsedAt: Number(item.lastUsedAt) || Date.now()
      }))
      .filter((item) => item.url.length > 0);
  } catch (error) {
    setStatus('Saved URL cache is invalid. Starting fresh.', 'error');
    return [];
  }
}

function persistSavedUrls(savedUrls) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(savedUrls));
}

function renderSavedUrls(savedUrls) {
  tableBody.innerHTML = '';

  if (savedUrls.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.textContent = 'No saved URLs yet. Preview a stream to save it.';
    cell.className = 'empty-state';
    row.appendChild(cell);
    tableBody.appendChild(row);
    return;
  }

  savedUrls.forEach((item) => {
    const row = document.createElement('tr');
    row.className = 'saved-row';
    row.title = 'Click to load this stream';

    const cell = document.createElement('td');
    cell.textContent = item.url;
    row.appendChild(cell);

    row.addEventListener('click', () => {
      urlInput.value = item.url;
      imageCanvas.src = item.url;
      setStatus('Loaded saved URL and updated preview.', 'success');
      markUrlAsUsed(item.url);
    });

    tableBody.appendChild(row);
  });
}

function markUrlAsUsed(url) {
  const normalizedUrl = url.trim();
  if (!normalizedUrl) {
    return;
  }

  const savedUrls = loadSavedUrls();
  const existingIndex = savedUrls.findIndex((item) => item.url === normalizedUrl);

  if (existingIndex >= 0) {
    savedUrls[existingIndex].lastUsedAt = Date.now();
  } else {
    savedUrls.push({
      url: normalizedUrl,
      lastUsedAt: Date.now()
    });
  }

  savedUrls.sort((a, b) => b.lastUsedAt - a.lastUsedAt);
  const nextSavedUrls = savedUrls.slice(0, MAX_SAVED_URLS);
  persistSavedUrls(nextSavedUrls);
  renderSavedUrls(nextSavedUrls);
}

document.getElementById('snapshot').addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  markUrlAsUsed(videoUrl);
  setStatus('Capturing snapshot...');
  const shell = new PythonShell('./python/camera_still.py', {
    mode: 'text',
    args: [videoUrl]
  });

  shell.on('message', (message) => {
    if (message.toLowerCase().includes('fail')) {
      setStatus('Snapshot failed. Check the URL and try again.', 'error');
      return;
    }

    setStatus('Snapshot saved successfully.', 'success');
  });

  shell.on('error', (error) => {
    setStatus(`Snapshot error: ${error.message}`, 'error');
  });
});

document.getElementById('record').addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  markUrlAsUsed(videoUrl);
  setStatus('Recording 5-second clip...');
  const shell = new PythonShell('./python/camera_record.py', {
    mode: 'text',
    args: [videoUrl]
  });

  shell.on('message', (message) => {
    if (message.toLowerCase().includes('success')) {
      setStatus('Recording complete. Video saved successfully.', 'success');
      return;
    }

    setStatus(message);
  });

  shell.on('error', (error) => {
    setStatus(`Recording error: ${error.message}`, 'error');
  });
});

document.getElementById('preview').addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  markUrlAsUsed(videoUrl);
  imageCanvas.src = videoUrl;
  setStatus('Preview updated.', 'success');
});

renderSavedUrls(loadSavedUrls());
