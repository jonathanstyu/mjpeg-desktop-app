// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.
var PythonShell = require('python-shell').PythonShell;
// const Store = require('electron-storage');

// const dataStore = new Store(); 

// let history = dataStore.get('history'); 

// if (history !== null && history.length > 0) {
//   let body = document.getElementById("tableBody"); 

//   for (var j = 0; j < history.length; j++) {
//     var tr = document.createElement('tr'); 
//     var tdElement = document.createElement('td'); 
//     tr.appendChild(tdElement); 
//     body.appendChild(tr);
//   }
// }

document.getElementById("snapshot").addEventListener("click", () => {
  let videobar = document.getElementById('urlInput').value; 
  let shell = new PythonShell('./python/camera_still.py', { 
    mode: "text",
    args: videobar
  }); 
  shell.on("message", (message) => {
    document.getElementById("alertbox").innerHTML = message
  })
  shell.send("Hello")
})

document.getElementById("record").addEventListener("click", () => {
  let videobar = document.getElementById('urlInput').value;
  let shell = new PythonShell('./python/camera_record.py', {
    mode: "text",
    args: videobar
  });
  shell.on("message", (message) => {
    console.log(message)
    document.getElementById("alertbox").innerHTML = message
  })
  shell.send("Hello")
})

document.getElementById('preview').addEventListener("click", () => {
  let videoUrl = document.getElementById('urlInput').value;
  document.getElementById("imageCanvas").src = videoUrl; 
})