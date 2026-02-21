// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.
const PythonShell = require('python-shell').PythonShell;

const STORAGE_KEY = 'mjpeg.savedUrls.v1';
const MAX_SAVED_URLS = 20;
const PYTHON_PATH = process.platform === 'win32' ? 'python' : 'python3';

const statusBox = document.getElementById('alertbox');
const urlInput = document.getElementById('urlInput');
const imageCanvas = document.getElementById('imageCanvas');
const tableBody = document.getElementById('tableBody');
const clipDurationSelect = document.getElementById('clipDuration');
const previewButton = document.getElementById('preview');
const snapshotButton = document.getElementById('snapshot');
const recordButton = document.getElementById('record');

let recordingTimerId = null;
let isRecording = false;

function setStatus(message, type = 'info') {
  statusBox.textContent = message;
  statusBox.classList.remove('success', 'error', 'recording');

  if (type === 'success') {
    statusBox.classList.add('success');
  } else if (type === 'error') {
    statusBox.classList.add('error');
  } else if (type === 'recording') {
    statusBox.classList.add('recording');
  }
}

function notifyUser(title, body) {
  if (typeof Notification === 'undefined') {
    return;
  }

  if (Notification.permission === 'granted') {
    new Notification(title, { body });
  }
}

if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
  Notification.requestPermission().catch(() => {});
}

function setRecordingUiState(active) {
  isRecording = active;
  recordButton.disabled = active;
  clipDurationSelect.disabled = active;
  previewButton.disabled = active;
  snapshotButton.disabled = active;
  recordButton.textContent = active ? 'Recording...' : 'Record Clip';
}

function startRecordingCountdown(durationSeconds) {
  if (recordingTimerId) {
    clearInterval(recordingTimerId);
  }

  const endAt = Date.now() + (durationSeconds * 1000);
  const renderTick = () => {
    const remainingSeconds = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
    setStatus(`Recording in progress... ${remainingSeconds}s remaining.`, 'recording');
  };

  renderTick();
  recordingTimerId = setInterval(renderTick, 250);
}

function stopRecordingCountdown() {
  if (recordingTimerId) {
    clearInterval(recordingTimerId);
    recordingTimerId = null;
  }
}

function getDependencyHelpMessage(errorMessage, actionLabel) {
  const normalized = String(errorMessage || '').toLowerCase();
  if (!normalized.includes('no module named') || !normalized.includes('cv2')) {
    return null;
  }

  return `${actionLabel} unavailable: OpenCV (cv2) is missing for ${PYTHON_PATH}. Run: ${PYTHON_PATH} -m pip install opencv-python`;
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

snapshotButton.addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  markUrlAsUsed(videoUrl);
  setStatus('Capturing snapshot...');
  const shell = new PythonShell('./python/camera_still.py', {
    mode: 'text',
    pythonPath: PYTHON_PATH,
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
    const dependencyMessage = getDependencyHelpMessage(error.message, 'Snapshot');
    if (dependencyMessage) {
      setStatus(dependencyMessage, 'error');
      return;
    }

    setStatus(`Snapshot error: ${error.message}`, 'error');
  });
});

recordButton.addEventListener('click', () => {
  if (isRecording) {
    setStatus('A recording is already in progress.', 'error');
    return;
  }

  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  const clipDuration = Number(clipDurationSelect.value) || 5;
  markUrlAsUsed(videoUrl);
  setRecordingUiState(true);
  startRecordingCountdown(clipDuration);
  notifyUser('Recording started', `Recording clip for ${clipDuration} seconds.`);
  const shell = new PythonShell('./python/camera_record.py', {
    mode: 'text',
    pythonPath: PYTHON_PATH,
    args: [videoUrl, String(clipDuration)]
  });
  let recordingFinished = false;

  shell.on('message', (message) => {
    if (message.toLowerCase().includes('success')) {
      recordingFinished = true;
      stopRecordingCountdown();
      setRecordingUiState(false);
      setStatus('Recording complete. Video saved successfully.', 'success');
      notifyUser('Recording complete', 'Video clip saved successfully.');
      return;
    }

    setStatus(message);
  });

  shell.on('error', (error) => {
    recordingFinished = true;
    stopRecordingCountdown();
    setRecordingUiState(false);
    const dependencyMessage = getDependencyHelpMessage(error.message, 'Recording');
    if (dependencyMessage) {
      setStatus(dependencyMessage, 'error');
      notifyUser('Recording failed', dependencyMessage);
      return;
    }

    setStatus(`Recording error: ${error.message}`, 'error');
    notifyUser('Recording failed', error.message);
  });

  shell.end((error, code) => {
    if (recordingFinished) {
      return;
    }

    stopRecordingCountdown();
    setRecordingUiState(false);

    if (error) {
      const dependencyMessage = getDependencyHelpMessage(error.message, 'Recording');
      if (dependencyMessage) {
        setStatus(dependencyMessage, 'error');
        notifyUser('Recording failed', dependencyMessage);
        return;
      }

      setStatus(`Recording error: ${error.message}`, 'error');
      notifyUser('Recording failed', error.message);
      return;
    }

    if (code === 0) {
      setStatus('Recording complete. Video saved successfully.', 'success');
      notifyUser('Recording complete', 'Video clip saved successfully.');
    } else {
      setStatus(`Recording stopped with exit code ${code}.`, 'error');
      notifyUser('Recording stopped', `Exit code ${code}.`);
    }
  });
});

previewButton.addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

  markUrlAsUsed(videoUrl);
  imageCanvas.src = videoUrl;
  setStatus('Preview updated.', 'success');
});

renderSavedUrls(loadSavedUrls());
