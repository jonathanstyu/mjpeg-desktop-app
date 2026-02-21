// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.
const PythonShell = require('python-shell').PythonShell;

const statusBox = document.getElementById('alertbox');
const urlInput = document.getElementById('urlInput');
const imageCanvas = document.getElementById('imageCanvas');

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

document.getElementById('snapshot').addEventListener('click', () => {
  const videoUrl = getVideoUrl();
  if (!videoUrl) {
    return;
  }

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

  imageCanvas.src = videoUrl;
  setStatus('Preview updated.', 'success');
});
